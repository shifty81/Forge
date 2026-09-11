#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
from ForgePYSettings import load_settings
from ForgePYPaths import data_root, projects_root, artifact_central_root, vault_root

VAULT_BOOTSTRAP_VERSION='FORGEPY-VAULT-BOOTSTRAP-0.1'

def layout() -> dict[str,Path]:
    home=data_root()
    return {
        'home':home, 'projects':projects_root(), 'artifactCentral':artifact_central_root(),
        'library':vault_root(), 'catalog':vault_root()/'catalog', 'forgeGit':home/'ForgeGit',
        'state':home/'State', 'logs':home/'Logs', 'components':home/'Components',
        'adapters':home/'Adapters', 'census':home/'Library'/'census',
    }

def ensure_layout() -> dict[str,Any]:
    paths=layout()
    made=[]
    for name,p in paths.items():
        if not p.exists(): made.append(name)
        p.mkdir(parents=True, exist_ok=True)
    return {'ok':True,'created':made,'paths':{k:str(v) for k,v in paths.items()}}
