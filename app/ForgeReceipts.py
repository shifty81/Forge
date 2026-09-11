#!/usr/bin/env python3
from __future__ import annotations
import json,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from ForgePYPaths import ensure_artifact_project_tree
RECEIPT_VERSION='FORGEPY-RECEIPT-1.0'
def write(project_id:str,kind:str,payload:dict[str,Any])->Path:
    root=ensure_artifact_project_tree(project_id)['reports']/'receipts'/kind; root.mkdir(parents=True,exist_ok=True); stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'); p=root/f'{stamp}.json'
    body={'schema':'forgepy.receipt.v1','version':RECEIPT_VERSION,'createdUtc':datetime.now(timezone.utc).isoformat(),'projectId':project_id,'kind':kind,**payload}
    fd,tmp=tempfile.mkstemp(prefix=p.name+'.',suffix='.tmp',dir=str(root))
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as fh:json.dump(body,fh,indent=2,sort_keys=True); fh.write('\n'); fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp,p)
    finally:
        try:os.unlink(tmp)
        except FileNotFoundError:pass
    return p
