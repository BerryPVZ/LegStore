#!/usr/bin/env python3
"""Import metadata only from the public 2015 TestFlight TSV; never fetch IPAs."""
import csv,gzip,hashlib,io,json,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://testflight.gstaaij.nl/'
FIELDS=['name','bundle_id','version','last_modified','minimum_os_version','platform_version','url','capture_date','warc_name','content_size']
def main():
 req=urllib.request.Request(SOURCE+'testflight_info.tsv.gz',headers={'User-Agent':'Mozilla/5.0 LegStore metadata indexer'})
 with urllib.request.urlopen(req,timeout=60) as response:
  with gzip.GzipFile(fileobj=response) as compressed:
   reader=csv.DictReader(io.TextIOWrapper(compressed,encoding='utf8'),delimiter='\t')
   if not set(FIELDS)<=set(reader.fieldnames or []):raise ValueError('Unexpected TSV schema')
   rows=[]
   for item in reader:
    rows.append([item.get(field,'') for field in FIELDS])
    if len(rows)>150000:raise ValueError('Unexpected index size')
 if len(rows)<80000:raise ValueError('Incomplete TestFlight index; previous export retained')
 out=ROOT/'data/testflight';out.mkdir(parents=True,exist_ok=True);chunks=[];total=0
 for start in range(0,len(rows),5000):
  batch=rows[start:start+5000];raw=json.dumps(batch,ensure_ascii=False,separators=(',',':')).encode('utf8');name='items-'+hashlib.sha256(raw).hexdigest()[:16]+'.json';(out/name).write_bytes(raw);total+=len(raw);chunks.append({'path':'data/testflight/'+name,'count':len(batch),'bytes':len(raw)})
 manifest={'source':SOURCE,'updated':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'count':len(rows),'bytes':total,'viewOnly':True,'schema':FIELDS,'chunks':chunks};tmp=out/'manifest.tmp';tmp.write_text(json.dumps(manifest,separators=(',',':')),encoding='utf8');tmp.replace(out/'manifest.json');print(json.dumps(manifest),flush=True)
if __name__=='__main__':main()
