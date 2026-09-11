#!/usr/bin/env python3
from __future__ import annotations
import json, shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from ForgeBackupRuntime import verify

RECOVERY_RUNTIME_VERSION="FORGEPY-RECOVERY-RUNTIME-1.0"

def restore_preview(backup:Path,destination:Path)->dict[str,Any]:
    check=verify(backup)
    return {'schema':'forgepy.restore-preview.v1','version':RECOVERY_RUNTIME_VERSION,
            'backup':str(backup),'destination':str(destination),'verified':check['ok'],
            'files':check['files'],'execute':False}

def database_backup(db_path:Path,destination_dir:Path)->Path:
    destination_dir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out=destination_dir/f'{db_path.stem}-{stamp}{db_path.suffix}.bak'
    shutil.copy2(db_path,out)
    return out
