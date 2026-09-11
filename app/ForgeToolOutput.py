#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
from ForgeToolContracts import ToolContract
TOOL_OUTPUT_VERSION='FORGEPY-TOOL-OUTPUT-1.0'
def capture(contract:ToolContract,project_root:Path)->list[dict[str,Any]]:
    rows=[];root=project_root.resolve()
    for spec in contract.outputs:
        pattern=spec.pattern or ''
        if not pattern:continue
        for p in root.glob(pattern):
            if not p.exists():continue
            try:rel=p.resolve().relative_to(root)
            except Exception:continue
            rows.append({'name':spec.name,'kind':spec.kind,'path':str(p),'relativePath':rel.as_posix(),'bytes':p.stat().st_size if p.is_file() else 0})
    return rows
