#!/usr/bin/env python3
from __future__ import annotations
import json,zipfile
from pathlib import Path
from typing import Any
CATALOG_VERSION='FORGEPY-BACKUP-CATALOG-1.0'
def inspect(path:Path)->dict[str,Any]:
    try:
        with zipfile.ZipFile(path) as z:data=json.loads(z.read('FORGEPY_BACKUP_MANIFEST.json'))
        return {'path':str(path),'valid':True,'createdUtc':data.get('createdUtc'),'source':data.get('source'),'files':len(data.get('files',[]))}
    except Exception as exc:return {'path':str(path),'valid':False,'error':str(exc)}
def scan(folder:Path)->list[dict[str,Any]]:return [inspect(p) for p in sorted(folder.glob('*.zip'),key=lambda p:p.stat().st_mtime,reverse=True)] if folder.is_dir() else []
