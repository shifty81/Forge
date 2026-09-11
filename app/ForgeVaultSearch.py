#!/usr/bin/env python3
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any
from ForgePYPaths import vault_root
VAULT_SEARCH_VERSION='FORGEPY-VAULT-SEARCH-1.0'
def db_path()->Path:return vault_root()/'catalog'/'drive_index.db'
def search(query:str, *, project_root:str='', classification:str='', limit:int=200, offset:int=0)->dict[str,Any]:
    p=db_path(); q=(query or '').strip(); lim=max(1,min(2000,int(limit))); off=max(0,int(offset))
    if not p.is_file():return {'rows':[],'total':0,'offset':off,'limit':lim}
    db=sqlite3.connect(p); db.row_factory=sqlite3.Row
    try:
        clauses=[]; args=[]
        if q:
            clauses.append('(name LIKE ? OR path LIKE ? OR note LIKE ? OR family_hint LIKE ?)'); like=f'%{q}%'; args += [like]*4
        if project_root: clauses.append('owner_project_root = ?'); args.append(project_root)
        if classification: clauses.append('classification = ?'); args.append(classification)
        where=(' WHERE '+' AND '.join(clauses)) if clauses else ''
        total=int(db.execute('SELECT COUNT(*) FROM entries'+where,args).fetchone()[0])
        rows=[dict(r) for r in db.execute('SELECT * FROM entries'+where+' ORDER BY path LIMIT ? OFFSET ?', [*args,lim,off]).fetchall()]
        return {'rows':rows,'total':total,'offset':off,'limit':lim,'hasMore':off+len(rows)<total}
    finally:db.close()


def classifications()->list[dict[str,Any]]:
    p=db_path()
    if not p.is_file(): return []
    db=sqlite3.connect(p)
    try:return [{'classification':r[0] or 'Unknown','count':int(r[1])} for r in db.execute('SELECT classification,COUNT(*) FROM entries GROUP BY classification ORDER BY COUNT(*) DESC').fetchall()]
    finally:db.close()

def owners(limit:int=200)->list[dict[str,Any]]:
    p=db_path()
    if not p.is_file(): return []
    db=sqlite3.connect(p)
    try:return [{'owner':r[0] or 'unassigned','count':int(r[1])} for r in db.execute('SELECT owner_project_root,COUNT(*) FROM entries GROUP BY owner_project_root ORDER BY COUNT(*) DESC LIMIT ?',(max(1,int(limit)),)).fetchall()]
    finally:db.close()
