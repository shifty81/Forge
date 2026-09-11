#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,zipfile
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from ForgePackagePolicy import is_governed

PATCH_BUILDER_VERSION="FORGEPY-PATCH-BUILDER-1.0"

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def _files(root:Path)->dict[str,Path]:
    out={}
    for p in root.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(root).as_posix()
        if is_governed(rel):out[rel]=p
    return out

def build(base:Path,target:Path,destination:Path,*,project:str='forgepy',base_build:str='',target_build:str='',target_version:str='',patch_id:str='',title:str='')->dict[str,Any]:
    base=base.resolve();target=target.resolve();old=_files(base);new=_files(target);rows=[]
    for rel in sorted(set(old)|set(new),key=str.casefold):
        a,b=old.get(rel),new.get(rel)
        if a and b and sha256_file(a)==sha256_file(b):continue
        if b is None:
            rows.append({'path':rel,'operation':'delete','preSha256':sha256_file(a),'allowMissing':False})
        else:
            row={'path':rel,'operation':'write','sha256':sha256_file(b),'bytes':b.stat().st_size}
            if a:row['preSha256']=sha256_file(a)
            rows.append(row)
    manifest={
        'schema':'forge.patch.v1','engine':'forge-universal','project':project,
        'patchId':patch_id or f'{project}-{target_build or target_version or "update"}',
        'title':title or f'{project} update',
        'createdUtc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'preconditions':{'projectBuild':base_build} if base_build else {},
        'target':{'projectBuild':target_build,'projectVersion':target_version},
        'files':rows,
    }
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('PATCH_MANIFEST.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        for row in rows:
            if row['operation']=='write':z.write(new[row['path']],'payload/'+row['path'])
    return {'path':str(destination),'files':len(rows),'manifest':manifest,'sha256':sha256_file(destination)}
