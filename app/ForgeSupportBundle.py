#!/usr/bin/env python3
from __future__ import annotations
import json, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from ForgeDependencyInventory import scan as dependency_scan
from ForgeEnvironmentFingerprint import capture as environment_capture
from ForgeSecurity import redact_text

SUPPORT_VERSION="FORGEPY-SUPPORT-BUNDLE-1.0"

def create(project_root:Path,destination:Path,extra:dict[str,Any]|None=None)->Path:
    destination.parent.mkdir(parents=True,exist_ok=True)
    report={'schema':'forgepy.support.v1','version':SUPPORT_VERSION,'createdUtc':datetime.now(timezone.utc).isoformat(),
            'projectRoot':str(project_root),'environment':environment_capture(),'dependencies':dependency_scan(project_root),
            'extra':extra or {}}
    safe=redact_text(json.dumps(report,indent=2,default=str))
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('support-report.json',safe)
        for candidate in ('project.control.json','README.md'):
            p=project_root/candidate
            if p.is_file(): z.writestr(candidate,redact_text(p.read_text(encoding='utf-8',errors='replace')))
    return destination
