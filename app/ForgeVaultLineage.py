#!/usr/bin/env python3
from __future__ import annotations
from collections import defaultdict
from typing import Any
LINEAGE_VERSION='FORGEPY-VAULT-LINEAGE-1.0'
def group(rows:list[dict[str,Any]])->list[dict[str,Any]]:
    buckets=defaultdict(list)
    for row in rows:
        key=str(row.get('family_hint') or row.get('owner_project_root') or 'unassigned')
        buckets[key].append(row)
    out=[]
    for key,items in buckets.items():
        hashes={str(x.get('sha256') or '') for x in items if x.get('sha256')}
        out.append({'family':key,'count':len(items),'distinctHashes':len(hashes),'bytes':sum(int(x.get('bytes') or 0) for x in items),'items':items})
    return sorted(out,key=lambda x:(-x['count'],x['family'].casefold()))
