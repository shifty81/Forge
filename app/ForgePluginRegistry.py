#!/usr/bin/env python3
from __future__ import annotations
import json
from dataclasses import dataclass,asdict,field
from pathlib import Path
from typing import Any
from ForgeVaultBootstrap import layout
PLUGIN_VERSION='FORGEPY-PLUGIN-REGISTRY-1.0'
@dataclass
class PluginSpec:
    plugin_id:str; name:str; version:str='0'; entrypoint:str=''; enabled:bool=False; approved:bool=False; permissions:tuple[str,...]=(); capabilities:tuple[str,...]=(); source:str='machine-local'
def path()->Path:return layout()['components']/'plugins'/'registry.json'
def load()->list[PluginSpec]:
    p=path()
    try:data=json.loads(p.read_text(encoding='utf-8-sig')) if p.is_file() else {}
    except Exception:data={}
    out=[]
    for row in data.get('plugins',[]) if isinstance(data,dict) else []:
        try:out.append(PluginSpec(**{k:v for k,v in row.items() if k in PluginSpec.__dataclass_fields__}))
        except Exception:pass
    return out
def save(items:list[PluginSpec])->Path:
    p=path(); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps({'schema':'forgepy.plugins.v1','version':PLUGIN_VERSION,'plugins':[asdict(x) for x in items]},indent=2)+'\n',encoding='utf-8');return p
def validate(spec:PluginSpec)->list[str]:
    errors=[]
    if not spec.plugin_id.strip():errors.append('plugin_id required')
    allowed={'project.read','project.write','process.run','network','vault.read','vault.write','source-control'}
    bad=[x for x in spec.permissions if x not in allowed]
    if bad:errors.append('unknown permissions: '+', '.join(bad))
    if spec.enabled and not spec.approved:errors.append('enabled plugin requires explicit approval')
    return errors
