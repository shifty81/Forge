#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

TAXONOMY_VERSION = "FORGEPY-COMMAND-TAXONOMY-1.0"
CATEGORY_ORDER = (
    "Build & Run", "Test / Validation", "Updates", "Source Control", "Assets",
    "World / Scene", "Tooling", "Diagnostics", "Packaging / Release", "Recovery",
    "Automation", "Developer / Advanced",
)
_PREFIX = {
    "build":"Build & Run", "run":"Build & Run", "launch":"Build & Run",
    "test":"Test / Validation", "gate":"Test / Validation", "validation":"Test / Validation", "verify":"Test / Validation",
    "patch":"Updates", "update":"Updates", "intake":"Updates",
    "git":"Source Control", "source":"Source Control", "forgegit":"Source Control", "github":"Source Control",
    "asset":"Assets", "content":"Assets", "world":"World / Scene", "scene":"World / Scene", "terrain":"World / Scene",
    "tool":"Tooling", "blender":"Tooling", "doctor":"Tooling", "dependency":"Tooling",
    "diagnostics":"Diagnostics", "audit":"Diagnostics", "health":"Diagnostics", "logs":"Diagnostics",
    "package":"Packaging / Release", "release":"Packaging / Release", "artifact":"Packaging / Release",
    "recovery":"Recovery", "restore":"Recovery", "repair":"Recovery", "backup":"Recovery",
    "automation":"Automation", "job":"Automation", "schedule":"Automation",
}

def category_for(key: str, declared: str='') -> str:
    declared=(declared or '').strip()
    if declared:
        d=declared.casefold()
        for canonical in CATEGORY_ORDER:
            if d == canonical.casefold(): return canonical
        if d in {'gate','validation','test'}: return 'Test / Validation'
        if d in {'build','run'}: return 'Build & Run'
        if d in {'package','release'}: return 'Packaging / Release'
        if d in {'diagnostics','audit'}: return 'Diagnostics'
        if d in {'source','git'}: return 'Source Control'
        if d in {'tool','tooling','blender'}: return 'Tooling'
    head=(key or '').strip().casefold().split('.',1)[0]
    return _PREFIX.get(head, 'Developer / Advanced')

def group_commands(commands: list[dict[str,Any]]) -> dict[str,list[dict[str,Any]]]:
    out={k:[] for k in CATEGORY_ORDER}
    for cmd in commands:
        cat=category_for(str(cmd.get('key') or ''), str(cmd.get('category') or ''))
        out.setdefault(cat,[]).append(cmd)
    return {k:v for k,v in out.items() if v}
