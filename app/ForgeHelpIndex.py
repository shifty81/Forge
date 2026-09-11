#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
HELP_INDEX_VERSION='FORGEPY-HELP-INDEX-1.0'
def build(docs:Path)->list[dict[str,Any]]:
    rows=[]
    for p in docs.rglob('*.md') if docs.is_dir() else []:
        text=p.read_text(encoding='utf-8',errors='replace');title=next((ln.lstrip('# ').strip() for ln in text.splitlines() if ln.startswith('#')) ,p.stem)
        rows.append({'title':title,'path':str(p),'relativePath':p.relative_to(docs).as_posix(),'bytes':p.stat().st_size})
    return sorted(rows,key=lambda x:x['title'].casefold())
