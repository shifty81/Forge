#!/usr/bin/env python3
from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from typing import Any
from ForgeVaultBootstrap import layout

UI_STATE_VERSION='FORGEPY-UI-STATE-1.0'

def path() -> Path: return layout()['state']/'ui-state.json'
def load() -> dict[str,Any]:
    p=path()
    try: data=json.loads(p.read_text(encoding='utf-8-sig')) if p.is_file() else {}
    except Exception: data={}
    return data if isinstance(data,dict) else {}
def save(data:dict[str,Any])->Path:
    p=path(); p.parent.mkdir(parents=True,exist_ok=True)
    body={'schema':'forgepy.ui-state.v1','version':UI_STATE_VERSION,**data}
    fd,tmp=tempfile.mkstemp(prefix=p.name+'.',suffix='.tmp',dir=str(p.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as fh: json.dump(body,fh,indent=2,sort_keys=True); fh.write('\n'); fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp,p)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
    return p
def get(namespace:str, default:Any=None)->Any: return load().get(namespace,default)
def set_value(namespace:str,value:Any)->Path:
    data=load(); data[namespace]=value; return save(data)
