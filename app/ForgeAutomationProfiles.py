#!/usr/bin/env python3
from __future__ import annotations
import json
from dataclasses import dataclass,asdict
from pathlib import Path
from ForgeVaultBootstrap import layout
AUTOMATION_VERSION='FORGEPY-AUTOMATION-1.0'
@dataclass
class AutomationProfile:
    profile_id:str; name:str; project_id:str; command:str; enabled:bool=False; trigger:str='manual'; condition:str=''; requires_confirmation:bool=True
def path()->Path:return layout()['state']/'automation-profiles.json'
def load()->list[AutomationProfile]:
    p=path()
    try:data=json.loads(p.read_text(encoding='utf-8-sig')) if p.is_file() else {}
    except Exception:data={}
    out=[]
    for row in data.get('profiles',[]) if isinstance(data,dict) else []:
        try:out.append(AutomationProfile(**row))
        except Exception:pass
    return out
def save(items:list[AutomationProfile])->Path:
    p=path(); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps({'schema':'forgepy.automation.v1','version':AUTOMATION_VERSION,'profiles':[asdict(x) for x in items]},indent=2)+'\n',encoding='utf-8');return p
