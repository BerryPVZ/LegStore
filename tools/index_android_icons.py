#!/usr/bin/env python3
"""Resumable real APK artwork extraction. Never saves an APK or IA thumbnail."""
import argparse,concurrent.futures,json,logging,sys,time,zipfile
from pathlib import Path
# Optional checkout-local install keeps dependencies out of Git.
ROOT=Path(__file__).resolve().parents[1]
if (ROOT/'.local/pydeps').exists():sys.path.insert(0,str(ROOT/'.local/pydeps'))
from pyaxmlparser.axmlprinter import AXMLPrinter
from pyaxmlparser.arscparser import ARSCParser
import index_sources as s
logging.getLogger('pyaxmlparser').setLevel(logging.ERROR)
ANDROID='{http://schemas.android.com/apk/res/android}'
def apk_icon(url,size):
 with zipfile.ZipFile(s.RemoteZip(url,size,max_read=12*1024*1024,budget=24*1024*1024)) as z:
  xml=AXMLPrinter(s.member(z,'AndroidManifest.xml',1024*1024)).get_xml_obj()
  app=xml.find('application')
  if app is None:raise ValueError('No application manifest')
  resources=None
  def paths(value):
   nonlocal resources
   if value.startswith('@'):
    if resources is None:resources=ARSCParser(s.member(z,'resources.arsc',12*1024*1024))
    result=resources.get_resolved_res_configs(int(value[1:].split(':')[-1],16))
    return [path for config,path in sorted(result,key=lambda item:item[0].get_density(),reverse=True) if isinstance(path,str)]
   return [value]
  ref=app.get(ANDROID+'icon') or app.get(ANDROID+'roundIcon')
  if not ref:raise ValueError('Manifest does not declare an app icon')
  candidates=paths(ref)
  for path in candidates:
   if not path.lower().endswith(('.png','.webp','.jpg','.jpeg')):continue
   try:
    raw=s.member(z,path);icon=s.compress_icon(raw)
    if icon:return icon,xml.get('package',''),path
   except (ValueError,OSError,KeyError):continue
  # Adaptive icons sometimes retain bitmap foreground/background resources.
  from PIL import Image
  for path in candidates:
   if not path.endswith('.xml'):continue
   try:
    adaptive=AXMLPrinter(s.member(z,path,256*1024)).get_xml_obj()
    if adaptive.tag!='adaptive-icon':continue
    canvas=Image.new('RGBA',(96,96),(0,0,0,0));parts=0
    for tag in ['background','foreground']:
     layer=adaptive.find(tag)
     if layer is None:continue
     value=layer.get(ANDROID+'drawable','')
     for candidate in paths(value):
      if candidate.lower().endswith(('.png','.webp','.jpg','.jpeg')):
       im=s.decode_image(s.member(z,candidate)).convert('RGBA');im.thumbnail((96,96));canvas.alpha_composite(im,((96-im.width)//2,(96-im.height)//2));parts+=1;break
    if parts==2:
     import io
     output=io.BytesIO();canvas.save(output,format='PNG');return s.compress_icon(output.getvalue()),xml.get('package',''),path
   except Exception:continue
  raise ValueError('No supported bitmap for declared launcher icon')
def process(row):
 ident=row[0]
 try:
  metadata=s.jsget('https://archive.org/metadata/'+s.urllib.parse.quote(ident,safe=''))
  files=[f for f in metadata.get('files',[]) if f['name'].lower().endswith('.apk')]
  if not files:return ident,{'status':'no-apk','files':{}}
  results={};errors=[];first=None;bundle=''
  for f in files:
   try:
    icon,package,member=apk_icon(s.archive_url(ident,f['name']),int(f.get('size',0)))
    results[f['name']]={'icon':icon,'member':member};first=first or icon;bundle=bundle or package
   except Exception as e:errors.append({'file':f['name'],'error':str(e)[:160]})
  return ident,{'status':'ready' if len(results)==len(files) else 'partial' if results else 'unavailable','icon':first or '', 'bundle':bundle,'files':results,'errors':errors}
 except Exception as e:return ident,{'status':'error','files':{},'error':str(e)[:160]}
def save(mapping):
 out=ROOT/'data/android/artwork.json';tmp=out.with_suffix('.tmp');doc={'updated':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'items':mapping};tmp.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf8');tmp.replace(out)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--limit',type=int,default=0,help='0 means the entire index');p.add_argument('--workers',type=int,default=4);p.add_argument('--retry-failed',action='store_true');args=p.parse_args()
 manifest=json.loads((ROOT/'data/android/manifest.json').read_text(encoding='utf8'));allrows=[]
 for chunk in manifest['chunks']:allrows+=json.loads((ROOT/chunk['path']).read_text(encoding='utf8'))
 out=ROOT/'data/android/artwork.json';mapping=json.loads(out.read_text(encoding='utf8'))['items'] if out.exists() else {}
 # Repair the visible/enriched selection first, then cover every indexed item.
 supplemental=json.loads((ROOT/'data/supplemental.json').read_text(encoding='utf8'))
 priority={a['archiveId']:i for i,a in enumerate(supplemental['apps']) if a.get('archiveId')}
 allrows.sort(key=lambda r:(priority.get(r[0],1000000),r[0]))
 rows=[r for r in allrows if r[0] not in mapping or (args.retry_failed and mapping[r[0]]['status'] in ('error','partial','unavailable'))]
 if args.limit:rows=rows[:args.limit]
 print(f'Queued {len(rows)} items; {len(mapping)} already processed',flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(args.workers,8))) as pool:
  futures={};iterator=iter(rows)
  def submit():
   try:row=next(iterator)
   except StopIteration:return
   futures[pool.submit(process,row)]=row[0]
  for _ in range(max(1,min(args.workers,8))):submit()
  completed=0
  while futures:
   done,_=concurrent.futures.wait(futures,return_when=concurrent.futures.FIRST_COMPLETED)
   for future in done:
    ident,result=future.result();mapping[ident]=result;del futures[future];completed+=1;submit()
    if completed%5==0:
     save(mapping);print(f'{completed}/{len(rows)} processed; {sum(bool(x.get("icon")) for x in mapping.values())} with real artwork',flush=True)
 save(mapping)
 print('Saved artwork manifest',flush=True)
if __name__=='__main__':main()
