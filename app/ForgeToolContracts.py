#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass,field,asdict
from pathlib import Path
from typing import Any

TOOL_CONTRACT_VERSION='FORGEPY-TOOL-CONTRACT-2.0'

@dataclass(frozen=True)
class ParameterSpec:
    name:str; kind:str='text'; required:bool=False; default:Any=None
    choices:tuple[str,...]=(); description:str=''; project_confined:bool=False

@dataclass(frozen=True)
class OutputSpec:
    name:str; kind:str='artifact'; pattern:str=''; description:str=''

@dataclass(frozen=True)
class ExecutionPolicy:
    timeout_seconds:int=300; mutation:str='read'; confirmation:bool=False
    allow_network:bool=True; max_output_bytes:int=8*1024*1024

@dataclass(frozen=True)
class ToolContract:
    tool_id:str; capability:str; parameters:tuple[ParameterSpec,...]=()
    outputs:tuple[OutputSpec,...]=(); policy:ExecutionPolicy=field(default_factory=ExecutionPolicy)
    version_requirement:str=''
    def to_dict(self)->dict[str,Any]:return asdict(self)

def coerce_value(spec:ParameterSpec,value:Any)->Any:
    if value is None: return spec.default
    if spec.kind in {'int','integer'}: return int(value)
    if spec.kind in {'float','number'}: return float(value)
    if spec.kind in {'bool','boolean'}:
        if isinstance(value,bool): return value
        return str(value).strip().casefold() in {'1','true','yes','on'}
    if spec.kind in {'path','file','folder'}: return str(Path(str(value)).expanduser())
    return str(value) if spec.kind in {'text','choice'} else value

def validate_values(contract:ToolContract,values:dict[str,Any], *, project_root:Path|None=None)->list[str]:
    errors=[]
    for p in contract.parameters:
        raw=values.get(p.name,p.default)
        if p.required and (raw is None or str(raw)==''):
            errors.append(f'{p.name} is required'); continue
        if raw is None: continue
        try:v=coerce_value(p,raw)
        except Exception as exc:
            errors.append(f'{p.name}: {exc}'); continue
        if p.choices and v not in p.choices:errors.append(f'{p.name} must be one of: {", ".join(p.choices)}')
        if p.project_confined and project_root is not None and p.kind in {'path','file','folder'}:
            try: Path(str(v)).resolve().relative_to(project_root.resolve())
            except Exception: errors.append(f'{p.name} must remain inside the project root')
    return errors

def resolved_values(contract:ToolContract,values:dict[str,Any])->dict[str,Any]:
    return {p.name:coerce_value(p,values.get(p.name,p.default)) for p in contract.parameters}
