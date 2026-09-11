#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, shlex, subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from ForgePYPaths import ensure_artifact_project_tree

TOOL_REGISTRY_VERSION='FORGEPY-TOOL-REGISTRY-1.0'
STATES=('DISCOVERED','CLASSIFIED','PROBED','READY','EXECUTABLE','VERIFIED','BLOCKED')

@dataclass
class ToolSpec:
    tool_id:str; name:str; project_id:str; root:str; path:str; capability:str; category:str
    kind:str; scope:str='project'; state:str='DISCOVERED'; interpreter:str=''; args:list[str]=field(default_factory=list)
    working_directory:str=''; mutates:bool=False; destructive:bool=False; source:str='scan'; reason:str=''; last_verified:str=''; version_requirement:str=''; probe:dict[str,Any]=field(default_factory=dict); parameters:list[dict[str,Any]]=field(default_factory=list); outputs:list[dict[str,Any]]=field(default_factory=list); timeout_seconds:int=300

def registry_path(project_id:str)->Path:
    return ensure_artifact_project_tree(project_id)['reports']/'tooling'/'tool-registry.json'
def save(project_id:str, tools:list[ToolSpec])->Path:
    path=registry_path(project_id); path.parent.mkdir(parents=True,exist_ok=True)
    payload={'schema':'forgepy.tool-registry.v1','version':TOOL_REGISTRY_VERSION,'projectId':project_id,'capturedUtc':datetime.now(timezone.utc).isoformat(),'tools':[asdict(x) for x in tools]}
    path.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8'); return path
def load(project_id:str)->list[ToolSpec]:
    path=registry_path(project_id)
    if not path.is_file(): return []
    try: data=json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception: return []
    out=[]
    for row in data.get('tools',[]):
        try: out.append(ToolSpec(**{k:v for k,v in row.items() if k in ToolSpec.__dataclass_fields__}))
        except Exception: pass
    return out

def run_tool(tool:ToolSpec, *, emit:Callable[[str],None]|None=None, extra_args:list[str]|None=None)->int:
    """Compatibility wrapper; ForgeToolRuntime is the sole execution authority."""
    from ForgeToolRuntime import execute
    result=execute(tool,emit=emit,extra_args=list(extra_args or []))
    return int(result.get("returncode") or 0)
