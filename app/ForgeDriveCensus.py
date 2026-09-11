#!/usr/bin/env python3
from __future__ import annotations
import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from ForgePYPaths import configured_scan_roots
from ForgeVaultBootstrap import layout

CENSUS_VERSION='FORGEPY-DRIVE-CENSUS-0.1'
SKIP={'.git','target','node_modules','.vs','__pycache__','.cache'}

def run(*, max_seconds: float=8.0, emit: Callable[[str],None]|None=None) -> dict:
    emit=emit or (lambda _x:None); started=time.monotonic(); files=dirs=bytes_total=0; truncated=False
    roots=[]
    for root in configured_scan_roots():
        if not root.exists(): continue
        roots.append(str(root)); emit(f'Census: {root}')
        for base, names, fnames in os.walk(root):
            names[:]=[n for n in names if n.casefold() not in SKIP]
            dirs += len(names)
            for fn in fnames:
                files += 1
                try: bytes_total += (Path(base)/fn).stat().st_size
                except OSError: pass
            if time.monotonic()-started > max_seconds:
                truncated=True; break
        if truncated: break
    payload={'schema':'forgepy.drive-census.v1','capturedUtc':datetime.now(timezone.utc).isoformat(),'roots':roots,'directories':dirs,'files':files,'bytes':bytes_total,'truncated':truncated}
    out=layout()['census']/'latest.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    return payload
