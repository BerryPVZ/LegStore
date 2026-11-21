#!/usr/bin/env python3
"""Cache every available TestFlight source icon as deduplicated 96px artwork."""
import argparse,concurrent.futures,http.client,json,threading,time,urllib.parse
from pathlib import Path
import index_sources as s
ROOT=Path(__file__).resolve().parents[1]
def icon_url(url):return 'https://testflight.gstaaij.nl/icons/'+urllib.parse.quote(url.removeprefix('http://').removeprefix('https://').replace('/','-'),safe='')
CONNECTIONS=threading.local()
def source_image(url):
 path=urllib.parse.urlsplit(url).path
 for attempt in range(2):
  connection=getattr(CONNECTIONS,'connection',None)
  if connection is None:connection=http.client.HTTPSConnection('testflight.gstaaij.nl',timeout=20);CONNECTIONS.connection=connection
  try:
   connection.request('GET',path,headers={'User-Agent':'Mozilla/5.0 LegStore icon cache','Accept':'image/*','Connection':'keep-alive'})
   response=connection.getresponse()
   if response.status!=200:
    response.read(4096);raise ValueError('Source HTTP '+str(response.status))
   if int(response.getheader('Content-Length','0'))>4*1024*1024:raise ValueError('Icon exceeds size budget')
   raw=response.read(4*1024*1024+1)
   if len(raw)>4*1024*1024:raise ValueError('Icon exceeds size budget')
   return raw
  except ValueError:
   connection.close();CONNECTIONS.connection=None;raise
  except Exception:
   connection.close();CONNECTIONS.connection=None
   if attempt:raise

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--limit',type=int,default=0);p.add_argument('--workers',type=int,default=6);p.add_argument('--retry-failed',action='store_true');args=p.parse_args()
 manifest=json.loads((ROOT/'data/testflight/manifest.json').read_text(encoding='utf8'));rows=[]
 for chunk in manifest['chunks']:rows+=json.loads((ROOT/chunk['path']).read_text(encoding='utf8'))
 output=ROOT/'data/testflight/artwork.json';old=json.loads(output.read_text(encoding='utf8')) if output.exists() else {};items=old.get('items',{});missing=old.get('missing',{});source_stamp=manifest['updated']
 if old.get('sourceUpdated') and old['sourceUpdated']!=source_stamp:raise ValueError('Source snapshot changed; rebuild artwork mapping explicitly')
 pending=[(i,row[6]) for i,row in enumerate(rows) if str(i) not in items and (str(i) not in missing or (args.retry_failed and '404' not in missing[str(i)]))]
 if args.limit:pending=pending[:args.limit]
 def process(entry):
  index,url=entry
  try:
   raw=source_image(icon_url(url));path=s.compress_icon(raw)
   if not path:raise ValueError('Source icon is unreadable')
   return str(index),path.rsplit('/',1)[-1],None
  except Exception as e:return str(index),None,str(e)[:100]
 def save():
  document={'sourceUpdated':source_stamp,'updated':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'total':len(rows),'cached':len(items),'attempted':len(items)+len(missing),'complete':len(items)+len(missing)==len(rows),'items':items,'missing':missing}
  temp=output.with_suffix('.tmp');temp.write_text(json.dumps(document,ensure_ascii=False,separators=(',',':')),encoding='utf8');temp.replace(output)
 print('TestFlight icons queued:',len(pending),'already cached:',len(items),flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(args.workers,8))) as pool:
  futures={};entries=iter(pending)
  def submit():
   if (ROOT/'.local/stop-testflight-icons').exists():return
   try:entry=next(entries)
   except StopIteration:return
   futures[pool.submit(process,entry)]=entry[0]
  for _ in range(max(1,min(args.workers,8))):submit()
  count=0
  while futures:
   done,_=concurrent.futures.wait(futures,return_when=concurrent.futures.FIRST_COMPLETED)
   for future in done:
    index,path,error=future.result();del futures[future]
    if path:items[index]=path;missing.pop(index,None)
    else:missing[index]=error
    count+=1;submit()
    if count%100==0:
     save();print('TestFlight icons:',len(items),'cached;',len(missing),'missing;',len(rows),'records',flush=True)
 save();print('TestFlight artwork checkpoint saved',flush=True)
if __name__=='__main__':main()
