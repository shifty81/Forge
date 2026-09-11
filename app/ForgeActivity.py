#!/usr/bin/env python3
from __future__ import annotations
import json,threading
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from ForgeVaultBootstrap import layout
ACTIVITY_VERSION='FORGEPY-ACTIVITY-1.0'; _LOCK=threading.Lock()
def path()->Path:return layout()['state']/'activity.jsonl'
def append(kind:str,project_id:str='',**payload:Any)->Path:
    p=path(); p.parent.mkdir(parents=True,exist_ok=True); row={'schema':'forgepy.activity.v1','version':ACTIVITY_VERSION,'utc':datetime.now(timezone.utc).isoformat(),'kind':kind,'projectId':project_id,**payload}
    with _LOCK:
        with p.open('a',encoding='utf-8',newline='\n') as fh:fh.write(json.dumps(row,sort_keys=True)+'\n')
    return p
def recent(limit:int=200,project_id:str='')->list[dict[str,Any]]:
    p=path(); wanted=max(1,int(limit))
    if not p.is_file():return []
    # Activity can become large. Read a bounded tail first, then filter.
    with p.open('rb') as fh:
        fh.seek(0,2); end=fh.tell(); size=min(end,max(65536,wanted*2048)); fh.seek(max(0,end-size))
        raw=fh.read().decode('utf-8',errors='replace')
    rows=[]
    for line in raw.splitlines():
        try:r=json.loads(line)
        except Exception:continue
        if project_id and r.get('projectId')!=project_id:continue
        rows.append(r)
    return rows[-wanted:]
