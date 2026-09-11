#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from ForgeToolPromotion import load,path
PROMOTION_MANAGER_VERSION='FORGEPY-TOOL-PROMOTION-MANAGER-1.0'
def request(tool_id:str,scope:str,project_family:str='',approved:bool=False)->Path:
    if scope not in {'project','family','global'}:raise ValueError('invalid scope')
    data=load();tools=data.setdefault('tools',{});tools[tool_id]={'scope':scope,'projectFamily':project_family,'approved':bool(approved),'updatedUtc':datetime.now(timezone.utc).isoformat()}
    p=path();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'schema':'forgepy.tool-promotions.v2','version':PROMOTION_MANAGER_VERSION,**data},indent=2)+'\n',encoding='utf-8');return p
def effective(tool_id:str)->dict[str,Any]:return dict((load().get('tools') or {}).get(tool_id) or {})
def allowed(tool_id:str)->bool:return bool(effective(tool_id).get('approved'))
