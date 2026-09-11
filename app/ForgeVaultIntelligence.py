#!/usr/bin/env python3
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from typing import Any

VAULT_INTELLIGENCE_VERSION="FORGEPY-VAULT-INTELLIGENCE-1.0"

def facets(rows:list[dict[str,Any]])->dict[str,Any]:
    classes=defaultdict(int); owners=defaultdict(int); families=defaultdict(int); extensions=defaultdict(int)
    duplicates=defaultdict(list)
    for row in rows:
        classes[str(row.get('classification') or 'Unknown')]+=1
        owners[str(row.get('owner_project_root') or 'unassigned')]+=1
        families[str(row.get('family_hint') or 'unassigned')]+=1
        extensions[str(row.get('extension') or '')]+=1
        h=str(row.get('sha256') or '')
        if h: duplicates[h].append(str(row.get('path') or ''))
    dup_groups=[{'sha256':h,'count':len(paths),'paths':paths} for h,paths in duplicates.items() if len(paths)>1]
    dup_groups.sort(key=lambda x:(-x['count'],x['sha256']))
    return {'version':VAULT_INTELLIGENCE_VERSION,'classifications':dict(classes),'owners':dict(owners),
            'families':dict(families),'extensions':dict(extensions),'duplicateGroups':dup_groups}

def ownership_confidence(row:dict[str,Any])->str:
    if row.get('owner_project_root') and row.get('family_hint'): return 'high'
    if row.get('owner_project_root'): return 'medium'
    return 'unclassified'
