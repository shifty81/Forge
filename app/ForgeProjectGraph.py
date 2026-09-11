#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
GRAPH_VERSION='FORGEPY-PROJECT-GRAPH-1.0'
def build(entries)->dict[str,Any]:
    nodes=[]; edges=[]
    normalized=[]
    for e in entries:
        root=Path(str(e.root)).resolve(); rid=str(getattr(e,'registry_id','') or getattr(e,'project_id','') or root)
        row={'id':rid,'projectId':str(getattr(e,'project_id','') or ''),'name':str(getattr(e,'name',root.name)),'root':str(root),'kind':str(getattr(e,'kind','project'))}; normalized.append((root,row)); nodes.append(row)
    for child,crow in normalized:
        candidates=[]
        for parent,prow in normalized:
            if parent==child:continue
            try: child.relative_to(parent); candidates.append((len(parent.parts),prow))
            except ValueError:pass
        if candidates:
            parent=max(candidates,key=lambda x:x[0])[1]; edges.append({'from':parent['id'],'to':crow['id'],'kind':'contains'})
    return {'schema':'forgepy.project-graph.v1','version':GRAPH_VERSION,'nodes':nodes,'edges':edges}
