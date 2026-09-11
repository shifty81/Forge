#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKUP_RUNTIME_VERSION="FORGEPY-BACKUP-RUNTIME-1.0"
DEFAULT_EXCLUDES={'.git','target','build','node_modules','.cache','__pycache__'}

def create(source:Path,destination:Path,*,exclude:set[str]|None=None,max_files:int=200000)->dict[str,Any]:
    source=source.resolve(); destination=destination.expanduser()
    destination.parent.mkdir(parents=True,exist_ok=True); exclude=exclude or DEFAULT_EXCLUDES
    rows=[]; count=0
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for p in source.rglob('*'):
            if not p.is_file(): continue
            rel=p.relative_to(source)
            if any(part in exclude for part in rel.parts): continue
            data=p.read_bytes(); digest=hashlib.sha256(data).hexdigest()
            z.writestr(rel.as_posix(),data); rows.append({'path':rel.as_posix(),'bytes':len(data),'sha256':digest})
            count+=1
            if count>=max_files: raise RuntimeError(f'backup file limit exceeded ({max_files})')
        manifest={'schema':'forgepy.backup.v1','version':BACKUP_RUNTIME_VERSION,'createdUtc':datetime.now(timezone.utc).isoformat(),'source':str(source),'files':rows}
        z.writestr('FORGEPY_BACKUP_MANIFEST.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return {'path':str(destination),'files':count,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}

def verify(path:Path)->dict[str,Any]:
    with zipfile.ZipFile(path,'r') as z:
        manifest=json.loads(z.read('FORGEPY_BACKUP_MANIFEST.json'))
        failures=[]
        for row in manifest.get('files',[]):
            try:data=z.read(row['path'])
            except KeyError: failures.append({'path':row['path'],'reason':'missing'}); continue
            if hashlib.sha256(data).hexdigest()!=row['sha256']: failures.append({'path':row['path'],'reason':'hash'})
        return {'ok':not failures,'files':len(manifest.get('files',[])),'failures':failures}
