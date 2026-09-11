#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
JOB_RECOVERY_VERSION='FORGEPY-JOB-RECOVERY-1.0'
def load(path:Path)->list[dict[str,Any]]:
    try:data=json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:return []
    return list(data.get('jobs') or []) if isinstance(data,dict) else []
def normalize_after_restart(rows:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for row in rows:
        r=dict(row)
        if r.get('state') in {'QUEUED','RUNNING'}:r['state']='INTERRUPTED';r['error']='ForgePY restarted before job completion'
        out.append(r)
    return out
