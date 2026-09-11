#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any
ADAPTER_SDK_VERSION='FORGEPY-ADAPTER-SDK-1.0'
@dataclass(frozen=True)
class AdapterCommand:
    capability:str; program:str; args:tuple[str,...]=(); category:str=''; mutates:bool=False; timeout_seconds:int=600
@dataclass(frozen=True)
class AdapterSpec:
    adapter_id:str; project_kinds:tuple[str,...]=(); commands:tuple[AdapterCommand,...]=(); priority:int=0; source:str='machine-local'
def validate(spec:AdapterSpec)->list[str]:
    errors=[]
    if not spec.adapter_id.strip():errors.append('adapter_id required')
    seen=set()
    for c in spec.commands:
        if not c.capability:errors.append('command capability required')
        if c.capability in seen:errors.append(f'duplicate capability: {c.capability}')
        seen.add(c.capability)
        if not c.program:errors.append(f'{c.capability}: program required')
    return errors
