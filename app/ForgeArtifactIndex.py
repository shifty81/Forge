#!/usr/bin/env python3
from __future__ import annotations
import sqlite3,time
from pathlib import Path
from typing import Any
from ForgePYPaths import artifact_central_root
ARTIFACT_INDEX_VERSION='FORGEPY-ARTIFACT-INDEX-1.0'
def db_path()->Path:return artifact_central_root()/'index'/'artifacts.db'
def _connect()->sqlite3.Connection:
    p=db_path(); p.parent.mkdir(parents=True,exist_ok=True); db=sqlite3.connect(p)
    db.executescript("CREATE TABLE IF NOT EXISTS artifacts(path TEXT PRIMARY KEY,project_id TEXT,category TEXT,name TEXT,extension TEXT,bytes INTEGER,mtime_ns INTEGER,last_seen REAL); CREATE INDEX IF NOT EXISTS idx_artifact_project ON artifacts(project_id); CREATE INDEX IF NOT EXISTS idx_artifact_category ON artifacts(category); CREATE INDEX IF NOT EXISTS idx_artifact_name ON artifacts(name);"); return db
def rebuild(max_files:int=250000)->dict[str,Any]:
    root=artifact_central_root(); db=_connect(); seen=0
    try:
        for p in root.rglob('*') if root.is_dir() else []:
            if not p.is_file() or p==db_path():continue
            try:st=p.stat()
            except OSError:continue
            rel=p.relative_to(root); parts=rel.parts; project=parts[1] if len(parts)>1 and parts[0]=='projects' else ''; category=parts[2] if len(parts)>2 and parts[0]=='projects' else ''
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET project_id=excluded.project_id,category=excluded.category,name=excluded.name,extension=excluded.extension,bytes=excluded.bytes,mtime_ns=excluded.mtime_ns,last_seen=excluded.last_seen',(str(p),project,category,p.name,p.suffix.casefold(),st.st_size,st.st_mtime_ns,time.time())); seen+=1
            if seen>=max_files:break
        db.commit(); return {'indexed':seen,'truncated':seen>=max_files,'database':str(db_path())}
    finally:db.close()
def search(query:str='',project_id:str='',category:str='',limit:int=200,offset:int=0)->dict[str,Any]:
    db=_connect(); db.row_factory=sqlite3.Row
    try:
        clauses=[]; args=[]
        if query:clauses.append('(name LIKE ? OR path LIKE ?)'); args += [f'%{query}%',f'%{query}%']
        if project_id:clauses.append('project_id=?'); args.append(project_id)
        if category:clauses.append('category=?'); args.append(category)
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        total=int(db.execute('SELECT COUNT(*) FROM artifacts'+where,args).fetchone()[0]); lim=max(1,min(2000,int(limit))); off=max(0,int(offset))
        rows=[dict(x) for x in db.execute('SELECT * FROM artifacts'+where+' ORDER BY mtime_ns DESC LIMIT ? OFFSET ?',[*args,lim,off]).fetchall()]
        return {'rows':rows,'total':total,'offset':off,'limit':lim,'hasMore':off+len(rows)<total}
    finally:db.close()


def purge_missing(limit:int=10000)->dict[str,Any]:
    db=_connect(); removed=0
    try:
        rows=db.execute('SELECT path FROM artifacts LIMIT ?', (max(1,int(limit)),)).fetchall()
        for (raw,) in rows:
            if not Path(raw).exists():
                db.execute('DELETE FROM artifacts WHERE path=?',(raw,)); removed+=1
        db.commit(); return {'removed':removed}
    finally: db.close()

def categories()->list[dict[str,Any]]:
    db=_connect()
    try:
        return [{'category':r[0] or 'unknown','count':int(r[1])} for r in db.execute('SELECT category,COUNT(*) FROM artifacts GROUP BY category ORDER BY COUNT(*) DESC').fetchall()]
    finally: db.close()
