#!/usr/bin/env python3
from __future__ import annotations
import os,subprocess
from pathlib import Path
from typing import Any
from ForgeSourceAuthority import safe_branch_name
GIT_MANAGER_VERSION='FORGEPY-GIT-MANAGER-1.0'
def _run(root:Path,args:list[str])->dict[str,Any]:
    cp=subprocess.run(['git',*args],cwd=root,capture_output=True,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'},creationflags=int(getattr(subprocess,'CREATE_NO_WINDOW',0)) if os.name=='nt' else 0)
    return {'ok':cp.returncode==0,'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr,'args':args}
def create_branch(root:Path,name:str,start:str='HEAD',switch:bool=True):
    name=safe_branch_name(name);return _run(root,['switch','-c',name,start] if switch else ['branch',name,start])
def switch_branch(root:Path,name:str):return _run(root,['switch',safe_branch_name(name)])
def tag(root:Path,name:str,ref:str='HEAD',message:str=''):
    args=['tag'];args+=['-a',name,'-m',message] if message else [name];args.append(ref);return _run(root,args)
def merge_preview(root:Path,source:str)->dict[str,Any]:return {'schema':'forgepy.merge-preview.v1','source':safe_branch_name(source),'commands':[['git','merge','--no-commit','--no-ff',safe_branch_name(source)]],'automatic':False}
