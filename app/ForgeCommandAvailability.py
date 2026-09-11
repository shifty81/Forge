#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
AVAILABILITY_VERSION='FORGEPY-COMMAND-AVAILABILITY-1.0'
def matrix(commands:list[dict[str,Any]],capabilities:set[str],tool_states:dict[str,str]|None=None)->list[dict[str,Any]]:
    tool_states=tool_states or {};rows=[]
    for c in commands:
        key=str(c.get('key') or c.get('command') or '')
        required=set(c.get('requires') or [])
        missing=sorted(required-capabilities)
        tool=str(c.get('toolId') or '')
        if tool and tool_states.get(tool) not in {'READY','EXECUTABLE','VERIFIED'}:missing.append('tool:'+tool)
        rows.append({**c,'available':not missing,'missing':missing})
    return rows
