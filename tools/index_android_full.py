#!/usr/bin/env python3
"""Export all APK Archive item identifiers/titles with cursor pagination.
No APKs or images are downloaded. Per-item APK metadata is resolved on demand.
"""
import argparse,json,time,urllib.request,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def fetch_page(cursor=None):
 params={'q':'collection:apkarchive','fields':'identifier,title','count':10000}
 if cursor:params['cursor']=cursor
 url='https://archive.org/services/search/v1/scrape?'+urllib.parse.urlencode(params)
 for attempt in range(5):
  try:
   request=urllib.request.Request(url,headers={'User-Agent':'LegStore indexer (github.com/BerryPVZ/LegStore)'})
   with urllib.request.urlopen(request,timeout=60) as r:
    raw=r.read(12*1024*1024+1)
   if len(raw)>12*1024*1024:raise ValueError('Metadata response exceeds limit')
   doc=json.loads(raw)
   if not isinstance(doc.get('items'),list):raise ValueError('Invalid archive response')
   return doc
  except Exception:
   if attempt==4:raise
   time.sleep(2**attempt)
def collect(fetch=fetch_page,progress=print):
 rows={};cursor=None;seen=set();expected=None
 while True:
  doc=fetch(cursor)
  if expected is None:expected=doc.get('total')
  items=doc['items']
  for item in items:
   ident=item.get('identifier')
   if ident:rows[ident]=[ident,str(item.get('title') or ident)]
  progress(f'{len(rows):,} items indexed',flush=True)
  next_cursor=doc.get('cursor')
  if not items or not next_cursor:break
  if next_cursor in seen:raise ValueError('Repeated cursor; refusing incomplete export')
  seen.add(next_cursor);cursor=next_cursor
 if not rows:raise ValueError('Empty export; previous index retained')
 # Collections can change during the traversal, but large losses must not publish.
 if expected and len(rows)<expected*0.99:raise ValueError(f'Incomplete export: {len(rows)} of approximately {expected}')
 return sorted(rows.values(),key=lambda r:r[0]),expected
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--chunk-size',type=int,default=10000);args=parser.parse_args()
 if args.chunk_size<100:parser.error('chunk size must be at least 100')
 rows,expected=collect();out=ROOT/'data/android';out.mkdir(parents=True,exist_ok=True)
 # Content-addressed chunks keep the old manifest valid until all files are ready.
 import hashlib
 chunks=[];size=0
 for start in range(0,len(rows),args.chunk_size):
  entries=rows[start:start+args.chunk_size];raw=json.dumps(entries,ensure_ascii=False,separators=(',',':')).encode('utf8');digest=hashlib.sha256(raw).hexdigest()[:16];name='items-'+digest+'.json';(out/name).write_bytes(raw);size+=len(raw);chunks.append({'path':'data/android/'+name,'count':len(entries),'bytes':len(raw)})
 manifest={'updated':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'collection':'apkarchive','count':len(rows),'reportedTotalAtStart':expected,'complete':True,'schema':['identifier','title'],'bytes':size,'chunks':chunks}
 temp=out/'manifest.tmp';temp.write_text(json.dumps(manifest,separators=(',',':')),encoding='utf8');temp.replace(out/'manifest.json')
 referenced={Path(c['path']).name for c in chunks}
 for path in out.glob('items-*.json'):
  if path.name not in referenced:path.unlink()
 print(json.dumps(manifest),flush=True)
if __name__=='__main__':main()
