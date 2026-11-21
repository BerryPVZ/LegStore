#!/usr/bin/env python3
"""Build LegStore's supplemental catalog without saving APK/IPA packages.

Only metadata, ZIP directory slices, Info.plist and icon members may be read.
All HTTP responses and archive-member reads are bounded. Existing iOS data is
preserved. Android's entire collection remains searchable through live paging.
"""
from pathlib import Path
import argparse,base64,concurrent.futures,hashlib,io,json,os,plistlib,re,struct,time,urllib.parse,urllib.request,zipfile,zlib
from PIL import Image,ImageOps
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data';ICONS=DATA/'icons';ICONS.mkdir(exist_ok=True,parents=True)
FOLDER='B2pShKDY';KEY='xl5HF4oL7cS8fvKxtCoaiA'
FOOD='com.tomatoflix.foodfight-ios3.0-clutch-2.0.4_202610'
UA={'User-Agent':'LegStore metadata-only indexer (github.com/BerryPVZ/LegStore)'}
STATS={'http_bytes':0,'icons_written':0,'packages_saved':0}

def fetch(url,limit=8*1024*1024,data=None,headers=None):
 req=urllib.request.Request(url,data=data,headers={**UA,**(headers or {})})
 with urllib.request.urlopen(req,timeout=25) as response:
  raw=response.read(limit+1)
  if len(raw)>limit:raise ValueError('Response exceeds metadata/icon budget')
  STATS['http_bytes']+=len(raw)
  return raw,dict(response.headers)
def jsget(url,**kwargs):return json.loads(fetch(url,**kwargs)[0])
def b64(s):return base64.urlsafe_b64decode(s+'='*(-len(s)%4))
def enc64(b):return base64.urlsafe_b64encode(b).decode().rstrip('=')
def archive_url(identifier,name):return 'https://archive.org/download/'+urllib.parse.quote(identifier,safe='')+'/'+urllib.parse.quote(name,safe='/')
def search_archive(query,page=1,rows=100):
 params={'q':query,'fl[]':['identifier','title','description','date'],'rows':rows,'page':page,'output':'json','sort[]':'downloads desc'}
 return jsget('https://archive.org/advancedsearch.php?'+urllib.parse.urlencode(params,doseq=True))['response']

class RemoteZip(io.RawIOBase):
 """A bounded, seekable HTTP-range reader; never falls back to a full package."""
 def __init__(self,url,size,aes=None):self.url=url;self.size=int(size);self.pos=0;self.aes=aes;self.used=0
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,offset,whence=0):
  self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
  if self.pos<0:raise ValueError('Negative seek')
  return self.pos
 def read(self,n=-1):
  if n<0:n=self.size-self.pos
  n=min(n,self.size-self.pos)
  if n<=0:return b''
  if n>1024*1024 or self.used+n>2*1024*1024:raise ValueError('ZIP range budget exceeded')
  start=self.pos;end=start+n-1
  raw,headers=fetch(self.url,limit=n+32,headers={'Range':f'bytes={start}-{end}'})
  cr=next((v for k,v in headers.items() if k.lower()=='content-range'),'')
  if not cr.startswith(f'bytes {start}-'):raise ValueError('Host did not honor HTTP Range; full package refused')
  self.used+=len(raw);self.pos+=len(raw)
  if self.aes:
   key,nonce=self.aes;block=start//16;skip=start%16
   counter=int.from_bytes(nonce,'big')+block
   decrypt=Cipher(algorithms.AES(key),modes.CTR(counter.to_bytes(16,'big'))).decryptor()
   raw=decrypt.update(bytes(skip)+raw)[skip:]
  return raw

def member(z,name,limit=512*1024):
 item=z.getinfo(name)
 if item.file_size>limit or item.compress_size>limit:raise ValueError('Archive member too large')
 with z.open(item) as f:
  data=f.read(limit+1)
 if len(data)>limit:raise ValueError('Member limit exceeded')
 return data
def zip_icon(url,size,aes=None,ios=False):
 with zipfile.ZipFile(RemoteZip(url,size,aes)) as z:
  metadata={}
  if ios:
   path=next((x for x in z.namelist() if re.fullmatch(r'Payload/[^/]+\.app/Info.plist',x)),None)
   if path:
    p=plistlib.loads(member(z,path,256*1024));metadata={'title':p.get('CFBundleDisplayName') or p.get('CFBundleName'),'bundle':p.get('CFBundleIdentifier'),'version':str(p.get('CFBundleShortVersionString') or p.get('CFBundleVersion') or ''),'minOS':p.get('MinimumOSVersion','')}
  candidates=[]
  for item in z.infolist():
   name=item.filename.lower()
   if not name.endswith(('.png','.webp','.jpg','.jpeg')) or item.file_size>512*1024:continue
   if not any(term in name for term in ['icon','launcher','appicon']):continue
   score=(40 if 'launcher' in name else 20)+(12 if 'xxxhdpi' in name else 9 if 'xxhdpi' in name else 6 if '@2x' in name else 0)-(30 if any(t in name for t in ['facebook','google','notification','small']) else 0)
   candidates.append((score,item.filename))
  for _,name in sorted(candidates,reverse=True)[:6]:
   try:
    raw=member(z,name);im=decode_image(raw)
    if im.width<32 or im.height<32:continue
    return raw,metadata
   except (ValueError,OSError):continue
  return None,metadata

def decode_image(raw):
 # Older iOS packages contain Apple CgBI PNGs (raw-deflate BGRA pixels).
 if raw.startswith(b'\x89PNG') and b'CgBI' in raw[:40]:
  pos=8;payload=b'';width=height=0
  while pos+12<=len(raw):
   length=int.from_bytes(raw[pos:pos+4],'big');kind=raw[pos+4:pos+8];chunk=raw[pos+8:pos+8+length];pos+=12+length
   if kind==b'IHDR':width,height,depth,color=struct.unpack('>IIBB',chunk[:10])
   if kind==b'IDAT':payload+=chunk
  if not width or width*height>4_000_000 or depth!=8 or color!=6:raise ValueError('Unsupported CgBI icon')
  pixels=zlib.decompress(payload,-15);stride=width*4;out=bytearray();prev=bytearray(stride)
  for y in range(height):
   off=y*(stride+1);kind=pixels[off];line=bytearray(pixels[off+1:off+1+stride])
   for x in range(stride):
    a=line[x-4] if x>=4 else 0;b=prev[x];c=prev[x-4] if x>=4 else 0
    if kind==1:v=a
    elif kind==2:v=b
    elif kind==3:v=(a+b)//2
    elif kind==4:
     pred=a+b-c;dist=[abs(pred-a),abs(pred-b),abs(pred-c)];v=[a,b,c][dist.index(min(dist))]
    elif kind==0:v=0
    else:raise ValueError('Invalid PNG filter')
    line[x]=(line[x]+v)&255
   for x in range(0,stride,4):
    blue,green,red,alpha=line[x:x+4]
    out.extend((min(255,red*255//alpha) if alpha else 0,min(255,green*255//alpha) if alpha else 0,min(255,blue*255//alpha) if alpha else 0,alpha))
   prev=line
  return Image.frombytes('RGBA',(width,height),bytes(out))
 im=Image.open(io.BytesIO(raw));im.load();return im

def compress_icon(raw):
 try:
  if not raw:return None
  im=decode_image(raw);im=ImageOps.exif_transpose(im).convert('RGBA');im.thumbnail((96,96),Image.Resampling.LANCZOS)
  # Pixel hashes deduplicate the same app artwork across sources/versions.
  digest=hashlib.sha256(im.tobytes()+str(im.size).encode()).hexdigest()[:18]
  webp=ICONS/(digest+'.webp');jpg=ICONS/(digest+'.jpg')
  if not webp.exists():
   im.save(webp,'WEBP',quality=68,method=6)
   bg=Image.new('RGB',im.size,'#f1f3f5');bg.paste(im,mask=im.getchannel('A'));bg.save(jpg,'JPEG',quality=72,optimize=True)
   STATS['icons_written']+=1
  return 'data/icons/'+digest
 except (ValueError,OSError,Image.DecompressionBombError):return None

def title_from_filename(name):
 name=re.sub(r'^[a-fA-F0-9]{32}_','',name)
 bundle=re.search(r'\(([^()]*\.[^()]+)\)',name)
 version=re.search(r'(?:_v?|[ -]v)(\d+(?:\.\d+){0,4})',name)
 title=name.split('_(')[0] if '_(' in name else re.split(r'[_-]v?\d',name,1)[0]
 title=re.sub(r'\.(ipa|apk)$','',title,flags=re.I).replace('_',' ').strip(' -')
 return title,bundle.group(1) if bundle else '',version.group(1) if version else ''

def legacy_lookup():
 rows=json.loads((DATA/'ipa.json').read_text(encoding='utf8'));by_bundle={};by_title={}
 for row in rows:
  icon=row[9] if len(row)>9 and row[9] else row[0]
  by_bundle.setdefault(row[4].lower(),icon);by_title.setdefault(re.sub(r'[^a-z0-9]','',row[3].lower()),icon)
 return by_bundle,by_title
LEGACY_BUNDLE,LEGACY_TITLE=legacy_lookup()
REUSED_CACHE={}
def reused_icon(bundle,title):
 ident=LEGACY_BUNDLE.get(bundle.lower()) if bundle else None
 if ident is None:ident=LEGACY_TITLE.get(re.sub(r'[^a-z0-9]','',title.lower()))
 if not ident:return None
 path='data/'+str(ident//1000)+'/'+str(ident)+'.jpg'
 if path not in REUSED_CACHE:
  try:REUSED_CACHE[path]=compress_icon(fetch('https://raw.githubusercontent.com/BerryPVZ/LegStore/main/'+path,limit=512*1024)[0]) or path
  except Exception:REUSED_CACHE[path]=path
 return REUSED_CACHE[path]

def mega_api(command):
 return jsget('https://g.api.mega.co.nz/cs?'+urllib.parse.urlencode({'id':int(time.time()*1000),'n':FOLDER}),data=json.dumps([command]).encode(),headers={'Content-Type':'application/json'})[0]
def decode_nodes(data):
 key=b64(KEY);nodes=[]
 for n in data['f']:
  try:
   encrypted=next(s.split(':',1)[1] for s in n['k'].split('/') if s.startswith(n['h']+':') or s.startswith(data['f'][0]['h']+':'))
   raw=Cipher(algorithms.AES(key),modes.ECB()).decryptor().update(b64(encrypted))
   aes=bytes(a^b for a,b in zip(raw[:16],raw[16:])) if len(raw)==32 else raw
   attrs=Cipher(algorithms.AES(aes),modes.CBC(bytes(16))).decryptor().update(b64(n['a']))
   if not attrs.startswith(b'MEGA'):continue
   n={**n,'name':json.loads(attrs[4:].rstrip(b'\0'))['n'],'aes':aes,'nonce':raw[16:24]+bytes(8)};nodes.append(n)
  except (KeyError,ValueError,StopIteration):continue
 return nodes
def mega_file(n):
 result=mega_api({'a':'g','g':1,'n':n['h']})
 if not isinstance(result,dict) or 'g' not in result:raise ValueError('MEGA download unavailable')
 return result['g']
def mega_icon(n):
 try:
  if n.get('s',0)>1024*1024:return None
  raw=fetch(mega_file(n),limit=1024*1024)[0]
  return Cipher(algorithms.AES(n['aes']),modes.CTR(n['nonce'])).decryptor().update(raw)
 except Exception:return None

def index_mega():
 nodes=decode_nodes(mega_api({'a':'f','c':1,'r':1,'ca':1}));images={}
 for n in nodes:
  if n.get('name','').lower().endswith(('.png','.jpg','.jpeg','.webp')):images[Path(n['name']).stem.lower()]=n
 apps=[n for n in nodes if n['name'].lower().endswith(('.ipa','.apk'))];out=[]
 def process(n):
  title,bundle,version=title_from_filename(n['name']);platform='android' if n['name'].lower().endswith('.apk') else 'ios'
  item={'id':'mega-'+n['h'],'title':title,'bundle':bundle,'version':version or 'Unspecified','platform':platform,'source':'mega','size':n.get('s',0),'minOS':'','filename':n['name'],'url':f'https://mega.nz/folder/{FOLDER}#{KEY}/file/{n["h"]}','device':'Unknown','category':'Games'}
  image=images.get(Path(n['name']).stem.lower());icon=compress_icon(mega_icon(image)) if image else None
  if not icon:icon=reused_icon(bundle,title)
  if not icon:
   try:
    raw,meta=zip_icon(mega_file(n),n['s'],(n['aes'],n['nonce']),platform=='ios');icon=compress_icon(raw)
    item.update({k:v for k,v in meta.items() if v})
   except Exception:pass
  item['icon']=icon or '';item['iconKind']='compressed' if icon and icon.startswith('data/icons/') else 'existing' if icon else 'fallback'
  return item
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for i,item in enumerate(pool.map(process,apps),1):
   out.append(item)
   if i%25==0:print('MEGA',i,'/',len(apps),flush=True)
 return out

def android_item(doc):
 ident=doc['identifier'];title=doc.get('title') or ident
 try:
  data=jsget('https://archive.org/metadata/'+urllib.parse.quote(ident,safe=''));files=[f for f in data.get('files',[]) if f['name'].lower().endswith('.apk')]
  if not files:return None
  images=[f for f in data.get('files',[]) if f['name'].lower().endswith(('.png','.webp','.jpg','.jpeg')) and int(f.get('size',0))<=512*1024]
  icon=None
  for f in sorted(images,key=lambda f:('icon' not in f['name'].lower(),'thumb' in f['name'].lower()))[:2]:
   try:icon=compress_icon(fetch(archive_url(ident,f['name']),limit=512*1024)[0])
   except Exception:pass
   if icon:break
  if not icon:
   try:icon=compress_icon(zip_icon(archive_url(ident,files[0]['name']),files[0].get('size',0))[0])
   except Exception:pass
  if not icon:
   try:icon=compress_icon(fetch('https://archive.org/services/img/'+urllib.parse.quote(ident,safe=''),limit=512*1024)[0])
   except Exception:pass
  variants=[{'version':title_from_filename(f['name'])[2] or 'Unspecified','filename':f['name'],'size':int(f.get('size',0)),'url':archive_url(ident,f['name'])} for f in files[:100]]
  return {'id':'ia-'+ident,'title':title,'bundle':'','version':variants[0]['version'],'platform':'android','source':'apkarchive','archiveId':ident,'size':variants[0]['size'],'minOS':'','filename':variants[0]['filename'],'url':variants[0]['url'],'icon':icon or '', 'iconKind':'compressed' if icon else 'fallback','device':'Android','category':'Apps','versions':variants,'archiveDate':doc.get('date',''),'details':'https://archive.org/details/'+ident}
 except Exception as e:
  print('Android metadata skipped:',ident,str(e)[:80],flush=True);return None

def index_android(limit):
 curated='collection:apkarchive AND (title:"Angry Birds" OR title:"Fruit Ninja" OR title:"Doodle Jump" OR title:"Cut the Rope" OR title:"Temple Run" OR title:"Plants vs Zombies" OR title:"Minecraft")'
 first=search_archive(curated,rows=min(limit,100));general=search_archive('collection:apkarchive',rows=min(limit,100));docs=[];seen=set()
 for doc in first['docs']+general['docs']:
  if doc['identifier'] not in seen:seen.add(doc['identifier']);docs.append(doc)
  if len(docs)>=limit:break
 out=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for i,item in enumerate(pool.map(android_item,docs),1):
   if item:out.append(item)
   if i%20==0:print('Android',i,'/',len(docs),flush=True)
 return out,general['numFound']

def index_food():
 d=jsget('https://archive.org/metadata/'+FOOD);out=[];icon=reused_icon('com.tomatoflix.foodfight','Food Fight')
 # Copy and compress the already-indexed artwork; no IPA download is needed.
 if icon and not icon.startswith('data/icons/'):
  try:icon=compress_icon(fetch('https://raw.githubusercontent.com/BerryPVZ/LegStore/main/'+icon,limit=512*1024)[0]) or icon
  except Exception:pass
 for f in d['files']:
  match=re.search(r'-v(1\.[012])-',f['name'])
  if not match or not f['name'].lower().endswith('.ipa'):continue
  out.append({'id':'foodfight-'+match[1],'title':'Food Fight','bundle':'com.tomatoflix.foodfight','version':match[1],'platform':'ios','source':'foodfight','size':int(f['size']),'minOS':'3.0','filename':f['name'],'url':archive_url(FOOD,f['name']),'icon':icon or '', 'iconKind':'compressed' if icon and icon.startswith('data/icons/') else 'existing','device':'iPhone / iPod touch','category':'Games','featured':True,'details':'https://archive.org/details/'+FOOD})
 assert {'1.0','1.1'}<={x['version'] for x in out},'Requested Food Fight versions missing'
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--android-limit',type=int,default=80);p.add_argument('--source',choices=['all','android','mega','foodfight'],default='all');args=p.parse_args()
 old=json.loads((DATA/'supplemental.json').read_text(encoding='utf8')) if (DATA/'supplemental.json').exists() else {'apps':[]}
 apps=old['apps'];total=old.get('androidCollectionTotal',0)
 for source,fn in [('foodfight',index_food),('mega',index_mega),('apkarchive',lambda:index_android(args.android_limit))]:
  if args.source not in ('all','android' if source=='apkarchive' else source):continue
  result=fn()
  if source=='apkarchive':result,total=result
  apps=[x for x in apps if x['source']!=source]+result
  print(source,len(result),'entries',flush=True)
 doc={'updated':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'androidCollectionTotal':total,'apps':apps,'stats':STATS}
 dest=DATA/'supplemental.json';tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf8');tmp.replace(dest)
 report={'entries':len(apps),'iconFiles':sum(1 for _ in ICONS.glob('*')),'iconBytes':sum(p.stat().st_size for p in ICONS.glob('*')),'catalogBytes':dest.stat().st_size,'missingIcons':[a['id'] for a in apps if not a.get('icon')],**STATS}
 (DATA/'source-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':main()
