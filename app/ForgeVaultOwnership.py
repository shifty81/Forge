#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
OWNERSHIP_VERSION='FORGEPY-VAULT-OWNERSHIP-1.0'
def score(path:Path,candidates:list[dict[str,Any]])->list[dict[str,Any]]:
    p=path.resolve();rows=[]
    for c in candidates:
        root=Path(str(c.get('root') or ''))
        points=0;reasons=[]
        try:rel=p.relative_to(root.resolve());points+=100;reasons.append('inside-root');points+=max(0,20-len(rel.parts))
        except Exception:pass
        fam=str(c.get('family') or c.get('family_hint') or '').casefold()
        if fam and fam in p.name.casefold():points+=10;reasons.append('family-name')
        if points:rows.append({'projectId':c.get('project_id') or c.get('projectId') or c.get('name'),'root':str(root),'score':points,'reasons':reasons})
    return sorted(rows,key=lambda r:(-r['score'],str(r['projectId'])))
def classify_confidence(rows:list[dict[str,Any]])->str:
    if not rows:return 'unclassified'
    if len(rows)==1 or rows[0]['score']-rows[1]['score']>=20:return 'high'
    return 'ambiguous'
