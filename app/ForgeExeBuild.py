#!/usr/bin/env python3
from __future__ import annotations
import subprocess,sys
from pathlib import Path
from typing import Any
from ForgeStandaloneBuild import preflight,command
EXE_BUILD_VERSION='FORGEPY-EXE-BUILD-1.0'
def plan(root:Path)->dict[str,Any]:
    info=preflight(root);return {'schema':'forgepy.exe-build-plan.v1','version':EXE_BUILD_VERSION,'preflight':info,'command':command(root),'requiresWindows':True,'automatic':False}
def execute(root:Path,*,approved:bool=False)->dict[str,Any]:
    p=plan(root)
    if not approved:raise PermissionError('standalone build requires explicit approval')
    if not p['preflight'].get('readyForWindowsBuild'):raise RuntimeError('Windows Nuitka preflight not ready')
    cp=subprocess.run(p['command'],cwd=root,capture_output=True,text=True,encoding='utf-8',errors='replace')
    return {'ok':cp.returncode==0,'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr}
