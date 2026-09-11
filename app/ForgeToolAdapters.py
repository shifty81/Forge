#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from ForgeToolRegistry import ToolSpec, load
from ForgeVaultBootstrap import layout

ADAPTER_VERSION='FORGEPY-GENERATED-ADAPTER-2.0'

def path_for(project_id:str)->Path: return layout()['adapters']/f'{project_id}.forgepy.adapter.json'
def generate(project_id:str, project_root:Path)->Path:
    tools=load(project_id); capabilities={}
    for tool in tools:
        if tool.state not in {'READY','EXECUTABLE','VERIFIED'}: continue
        capabilities.setdefault(tool.capability,[]).append(tool.tool_id)
    payload={'schema':'forgepy.generated-adapter.v1','version':ADAPTER_VERSION,'projectId':project_id,'projectRoot':str(project_root.resolve()),'generatedUtc':datetime.now(timezone.utc).isoformat(),'capabilities':capabilities,'authority':'machine-local-generated','precedence':'below project.control.json and project-owned CLI','contract':'forgepy.adapter.v2','nonDestructive':True}
    p=path_for(project_id); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8'); return p
