#!/usr/bin/env python3
from __future__ import annotations
import re
from typing import Mapping
SECURITY_V2_VERSION='FORGEPY-SECURITY-2.0'
SECRET_PATTERNS=[re.compile(r'(?i)(token|secret|password|api[_-]?key)\s*[:=]\s*([^\s,;]+)'),re.compile(r'gh[pousr]_[A-Za-z0-9_]{20,}')]
def redact(text:str)->str:
    out=str(text)
    for p in SECRET_PATTERNS:
        out=p.sub(lambda m:(m.group(1)+'=<redacted>') if m.lastindex and m.lastindex>=2 else '<redacted>',out)
    return out
def safe_env(env:Mapping[str,str],extra_allow:set[str]|None=None)->dict[str,str]:
    allow={'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','HOME','USERPROFILE','LOCALAPPDATA','APPDATA','PYTHONUTF8','PYTHONIOENCODING'}|(extra_allow or set())
    return {k:v for k,v in env.items() if k in allow and not re.search(r'(?i)(token|secret|password|key)$',k)}
