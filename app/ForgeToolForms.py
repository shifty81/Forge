#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import asdict
from typing import Any
from ForgeToolContracts import ToolContract,ParameterSpec
TOOL_FORMS_VERSION='FORGEPY-TOOL-FORMS-1.0'
def field_model(p:ParameterSpec)->dict[str,Any]:
    widget={'bool':'check','boolean':'check','choice':'combo','file':'file-picker','folder':'folder-picker','path':'path-picker','int':'number','integer':'number','float':'number','number':'number'}.get(p.kind,'text')
    return {'name':p.name,'kind':p.kind,'widget':widget,'required':p.required,'default':p.default,'choices':list(p.choices),'description':p.description,'projectConfined':p.project_confined}
def form_model(c:ToolContract)->dict[str,Any]:
    return {'schema':'forgepy.tool-form.v1','version':TOOL_FORMS_VERSION,'toolId':c.tool_id,'capability':c.capability,'fields':[field_model(x) for x in c.parameters],'outputs':[asdict(x) for x in c.outputs],'policy':asdict(c.policy)}
def cli_args(c:ToolContract,values:dict[str,Any])->list[str]:
    out=[]
    for p in c.parameters:
        if p.name not in values:continue
        v=values[p.name]
        if p.kind in {'bool','boolean'}:
            if bool(v):out.append(f'--{p.name}')
        else:out.extend([f'--{p.name}',str(v)])
    return out
