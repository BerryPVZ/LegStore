#!/usr/bin/env python3
"""Use another version of the same bundle only when the source icon is missing."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 source=json.loads((ROOT/'data/testflight/manifest.json').read_text(encoding='utf8'));rows=[]
 for chunk in source['chunks']:rows+=json.loads((ROOT/chunk['path']).read_text(encoding='utf8'))
 path=ROOT/'data/testflight/artwork.json';art=json.loads(path.read_text(encoding='utf8'));by_bundle={}
 for index,hash in art['items'].items():
  bundle=rows[int(index)][1].strip().lower()
  if bundle and bundle!='-':by_bundle.setdefault(bundle,hash)
 fallback={}
 for index in art.get('missing',{}):
  bundle=rows[int(index)][1].strip().lower()
  if bundle in by_bundle:fallback[index]=by_bundle[bundle]
 art['fallback']=fallback;art['fallbackKind']='same bundle, another archived version';art['displayable']=len(art['items'])+len(fallback);temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(art,ensure_ascii=False,separators=(',',':')),encoding='utf8');temporary.replace(path);print('TestFlight exact icons:',len(art['items']),'same-app fallbacks:',len(fallback),'unavailable:',source['count']-art['displayable'],flush=True)
if __name__=='__main__':main()
