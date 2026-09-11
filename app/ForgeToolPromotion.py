#!/usr/bin/env python3
from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from typing import Any
from ForgeVaultBootstrap import layout
PROMOTION_VERSION='FORGEPY-TOOL-PROMOTION-1.0'
def path()->Path:return layout()['adapters']/'tool-promotions.json'
def load()->dict[str,Any]:
    p=path()
    try:return json.loads(p.read_text(encoding='utf-8-sig')) if p.is_file() else {'tools':{}}
    except Exception:return {'tools':{}}
def promote(tool_id:str,scope:str,*,project_family:str='')->Path:
    if scope not in {'project','family','global'}:raise ValueError('scope must be project, family or global')
    data=load(); data.setdefault('tools',{})[tool_id]={'scope':scope,'projectFamily':project_family}
    p=path(); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps({'schema':'forgepy.tool-promotions.v1','version':PROMOTION_VERSION,**data},indent=2)+'\n',encoding='utf-8'); return p
