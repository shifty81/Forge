#!/usr/bin/env python3
from __future__ import annotations
import ast, json
from pathlib import Path
from typing import Any
from ForgeCleanPcMatrix import scenarios
from ForgeStandaloneBuild import preflight

CERTIFICATION_VERSION="FORGEPY-CERTIFICATION-1.0"

def static_audit(root:Path)->dict[str,Any]:
    py_files=[*root.joinpath('app').glob('*.py'),*root.joinpath('tools').glob('*.py')]
    failures=[]
    for p in py_files:
        try:ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
        except Exception as exc:failures.append({'path':str(p),'error':str(exc)})
    manifest=root/'FORGEPY_PACKAGE_MANIFEST.json'
    return {'schema':'forgepy.certification.v1','version':CERTIFICATION_VERSION,'syntaxOk':not failures,
            'syntaxFailures':failures,'manifestExists':manifest.is_file(),'standalone':preflight(root),
            'cleanPcScenarios':scenarios()}

def blockers(audit:dict[str,Any])->list[str]:
    rows=[]
    if not audit.get('syntaxOk'):rows.append('Python syntax failures')
    if not audit.get('manifestExists'):rows.append('package manifest missing')
    if not audit.get('standalone',{}).get('readyForWindowsBuild'):rows.append('Windows standalone build requires host certification')
    return rows
