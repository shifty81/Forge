#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app"
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
from ForgeVersion import VERSION, BUILD
OUTPUT=ROOT/"FORGE_PACKAGE_MANIFEST.json"
EXCLUDED_PARTS={"__pycache__",".git","artifacts","updates","logs"}
EXCLUDED_NAMES={"FORGE_PACKAGE_MANIFEST.json","VAULT_PACKAGE_MANIFEST.json"}
def main()->int:
    rows=[]
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file(): continue
        rel=path.relative_to(ROOT)
        if path.name in EXCLUDED_NAMES or any(part in EXCLUDED_PARTS for part in rel.parts): continue
        data=path.read_bytes(); rows.append({"path":rel.as_posix(),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    payload={"schema":"forge.package.manifest.v2","forgeVersion":VERSION,"forgeBuild":BUILD,"generatedUtc":datetime.now(timezone.utc).isoformat(),"fileCount":len(rows),"files":rows}
    OUTPUT.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"[PASS] wrote {OUTPUT} with {len(rows)} file(s)"); return 0
if __name__=="__main__": raise SystemExit(main())
