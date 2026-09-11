#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
RECOVERY_CATALOG_VERSION='FORGEPY-RECOVERY-CATALOG-1.0'
def discover(root:Path)->list[dict[str,Any]]:
    rows=[]
    for p in root.rglob('*') if root.is_dir() else []:
        if not p.is_file():continue
        low=p.name.casefold()
        kind='backup' if low.endswith(('.bak','.backup','.zip')) else ('receipt' if 'receipt' in low else '')
        if kind:rows.append({'path':str(p),'kind':kind,'mtime':p.stat().st_mtime,'bytes':p.stat().st_size})
    return sorted(rows,key=lambda r:-r['mtime'])
