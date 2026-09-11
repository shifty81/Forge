#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path
from typing import Any
SECURITY_VERSION='FORGEPY-SECURITY-1.0'
_SECRET_RE=re.compile(r'(?i)(token|password|secret|authorization|api[_-]?key)\s*[:=]\s*([^\s,;]+)')
def redact_text(text:str)->str:return _SECRET_RE.sub(lambda m:f'{m.group(1)}=<redacted>',str(text))
def confined(root:Path,path:Path)->bool:
    try:path.resolve().relative_to(root.resolve());return True
    except Exception:return False
def risk_for(mutates:bool=False,destructive:bool=False,network:bool=False)->str:
    if destructive:return 'destructive'
    if mutates:return 'write'
    if network:return 'network-read'
    return 'read'
