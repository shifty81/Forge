#!/usr/bin/env python3
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
from ForgeVaultBootstrap import ensure_layout, layout

FIRST_RUN_VERSION='FORGEPY-FIRST-RUN-1.0'

def marker_path() -> Path:return layout()['state']/'first-run.json'
def needed() -> bool:return not marker_path().is_file()
def plan()->dict:
    paths=layout()
    return {'schema':'forgepy.first-run-plan.v1','version':FIRST_RUN_VERSION,'needsSetup':needed(),
            'paths':{k:str(v) for k,v in paths.items()},
            'steps':['vault-layout','project-registry','forgegit','artifact-central','downloads-intake','background-census'],
            'automaticInstalls':False,'nonPatchMoves':False}
def initialize() -> dict:
    result=ensure_layout(); marker=marker_path(); marker.parent.mkdir(parents=True,exist_ok=True)
    payload={'schema':'forgepy.first-run.v1','version':FIRST_RUN_VERSION,'completedUtc':datetime.now(timezone.utc).isoformat(),
             'layout':result['paths'],'automaticInstalls':False,'nonPatchMoves':False}
    marker.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    return payload
