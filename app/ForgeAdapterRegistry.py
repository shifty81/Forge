#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from ForgeVaultBootstrap import layout

ADAPTER_REGISTRY_VERSION="FORGEPY-ADAPTER-REGISTRY-1.0"

def root()->Path:
    p=layout()['adapters']; p.mkdir(parents=True,exist_ok=True); return p

def load_all()->list[dict[str,Any]]:
    rows=[]
    for p in sorted(root().glob('*.forgepy.adapter.json')):
        try:
            data=json.loads(p.read_text(encoding='utf-8-sig')); data['_path']=str(p); rows.append(data)
        except Exception: continue
    return rows

def resolve(project_id:str, project_kind:str='')->list[dict[str,Any]]:
    matches=[]
    for row in load_all():
        score=0
        if str(row.get('projectId') or '')==project_id: score+=100
        kinds=row.get('projectKinds') or row.get('project_kinds') or []
        if project_kind and project_kind in kinds: score+=20
        if not score: continue
        matches.append((score,int(row.get('priority') or 0),row))
    return [r for _,_,r in sorted(matches,key=lambda x:(-x[0],-x[1],str(x[2].get('_path'))))]
