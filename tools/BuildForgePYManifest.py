#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app"
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION, BUILD
from ForgePackagePolicy import is_governed
OUTPUT=ROOT/"FORGEPY_PACKAGE_MANIFEST.json"
EXCLUDED_NAMES={"FORGEPY_PACKAGE_MANIFEST.json","FORGE_PACKAGE_MANIFEST.json","VAULT_PACKAGE_MANIFEST.json"}
def main()->int:
    rows=[]
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file(): continue
        rel=path.relative_to(ROOT)
        if path.name in EXCLUDED_NAMES or not is_governed(rel.as_posix()): continue
        data=path.read_bytes(); rows.append({"path":rel.as_posix(),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    generated=datetime.now(timezone.utc).isoformat()
    try:
        old=json.loads(OUTPUT.read_text(encoding="utf-8-sig")) if OUTPUT.is_file() else {}
        if old.get("forgePyVersion")==VERSION and old.get("forgePyBuild")==BUILD and old.get("files")==rows:
            generated=str(old.get("generatedUtc") or generated)
    except Exception: pass
    payload={"schema":"forgepy.package.manifest.v1","forgePyVersion":VERSION,"forgePyBuild":BUILD,"generatedUtc":generated,"fileCount":len(rows),"files":rows}
    encoded=json.dumps(payload,indent=2,sort_keys=True)+"\n"
    previous=OUTPUT.read_text(encoding="utf-8-sig") if OUTPUT.is_file() else ""
    if encoded!=previous: OUTPUT.write_text(encoded,encoding="utf-8")
    print(f"[PASS] wrote {OUTPUT} with {len(rows)} file(s)"); return 0
if __name__=="__main__": raise SystemExit(main())
