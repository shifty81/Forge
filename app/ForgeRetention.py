#!/usr/bin/env python3
from __future__ import annotations
import time
from pathlib import Path
from typing import Any
RETENTION_VERSION='FORGEPY-RETENTION-1.0'
def plan(root:Path, *, older_than_days:int=30, max_items:int=5000)->dict[str,Any]:
    cutoff=time.time()-max(0,int(older_than_days))*86400; rows=[]; bytes_total=0
    for p in root.rglob('*') if root.is_dir() else []:
        if not p.is_file():continue
        try:st=p.stat()
        except OSError:continue
        if st.st_mtime<cutoff:rows.append({'path':str(p),'bytes':st.st_size,'mtime':st.st_mtime});bytes_total+=st.st_size
        if len(rows)>=max_items:break
    return {'schema':'forgepy.retention-plan.v1','version':RETENTION_VERSION,'root':str(root),'olderThanDays':older_than_days,'items':rows,'bytes':bytes_total,'destructive':False}
