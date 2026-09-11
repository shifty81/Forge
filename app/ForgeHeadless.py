#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
from PCCSurfaceCommon import ProjectContract,BackendClient
HEADLESS_VERSION='FORGEPY-HEADLESS-1.0'
def run(root:Path,command:str,extra:list[str]|None=None)->dict[str,Any]:
    contract=ProjectContract.load(root);backend=BackendClient(root,contract)
    if not backend.supports(command):return {'ok':False,'reason':'command unavailable','command':command}
    cp=backend.run(command,extra or [])
    return {'ok':cp.returncode==0,'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr,'command':command}
