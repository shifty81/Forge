#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any
RELEASE_VERSION='FORGEPY-RELEASE-1.0'
CHANNELS=('dev','preview','stable')
def manifest(version:str,build:str,files:list[Path],channel:str='preview')->dict[str,Any]:
    if channel not in CHANNELS:raise ValueError(channel)
    rows=[]
    for p in files:
        if not p.is_file():continue
        h=hashlib.sha256(p.read_bytes()).hexdigest();rows.append({'path':str(p),'bytes':p.stat().st_size,'sha256':h})
    return {'schema':'forgepy.release.v1','version':RELEASE_VERSION,'productVersion':version,'build':build,'channel':channel,'files':rows}
def readiness(checks:dict[str,bool])->dict[str,Any]:return {'ready':all(checks.values()),'checks':checks,'blockers':[k for k,v in checks.items() if not v]}
