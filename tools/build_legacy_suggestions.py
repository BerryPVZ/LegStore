#!/usr/bin/env python3
"""Build Seth's compact name/bundle list from every original LegStore app."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 rows=json.loads((ROOT/'data/ipa.json').read_text(encoding='utf8'));seen={}
 for row in rows:
  key=(row[4] or row[3]).strip().casefold()
  if key and key not in seen:seen[key]=[row[3],row[4]]
 output=ROOT/'data/legacy-suggestions.json';temporary=output.with_suffix('.tmp');temporary.write_text(json.dumps(list(seen.values()),ensure_ascii=False,separators=(',',':')),encoding='utf8');temporary.replace(output);print(len(seen),'original apps;',output.stat().st_size,'bytes')
if __name__=='__main__':main()
