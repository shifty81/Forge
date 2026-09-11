#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,shutil,tempfile,zipfile
from pathlib import Path
from typing import Any
from ForgeBackupRuntime import verify
RESTORE_VERSION='FORGEPY-RESTORE-TRANSACTION-1.0'
def plan(backup:Path,destination:Path)->dict[str,Any]:
    check=verify(backup)
    if not check['ok']:return {'ok':False,'reason':'backup verification failed','check':check}
    return {'schema':'forgepy.restore-plan.v1','version':RESTORE_VERSION,'ok':True,'backup':str(backup),'destination':str(destination),'files':check['files'],'requiresConfirmation':True,'automatic':False}
def execute(backup:Path,destination:Path,*,approved:bool=False)->dict[str,Any]:
    if not approved:raise PermissionError('restore requires explicit approval')
    p=plan(backup,destination)
    if not p['ok']:raise RuntimeError(p['reason'])
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    rollback=destination.parent/(destination.name+'.forgepy-restore-backup')
    if rollback.exists():shutil.rmtree(rollback)
    shutil.copytree(destination,rollback,dirs_exist_ok=True)
    staged=Path(tempfile.mkdtemp(prefix='forgepy-restore-',dir=str(destination.parent)))
    try:
        with zipfile.ZipFile(backup) as z:
            for name in z.namelist():
                if name=='FORGEPY_BACKUP_MANIFEST.json':continue
                target=(staged/name).resolve()
                try:target.relative_to(staged.resolve())
                except Exception:raise RuntimeError(f'unsafe backup path: {name}')
                z.extract(name,staged)
        for item in staged.iterdir():
            target=destination/item.name
            if item.is_dir():shutil.copytree(item,target,dirs_exist_ok=True)
            else:shutil.copy2(item,target)
        return {'ok':True,'rollback':str(rollback),'destination':str(destination)}
    except Exception:
        shutil.rmtree(destination,ignore_errors=True);shutil.copytree(rollback,destination,dirs_exist_ok=True);raise
    finally:shutil.rmtree(staged,ignore_errors=True)
