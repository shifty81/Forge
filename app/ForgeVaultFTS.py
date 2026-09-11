#!/usr/bin/env python3
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any,Iterable
from ForgeVaultBootstrap import layout
VAULT_FTS_VERSION='FORGEPY-VAULT-FTS-1.0'
TEXT_SUFFIXES={'.txt','.md','.json','.toml','.yaml','.yml','.py','.rs','.cpp','.h','.hpp','.c','.cs','.js','.ts','.html','.css','.xml','.ron'}
def db_path()->Path:
    p=layout()['library']/'catalog'/'content_fts.db';p.parent.mkdir(parents=True,exist_ok=True);return p
def _connect():
    db=sqlite3.connect(db_path());db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE IF NOT EXISTS docs(path TEXT PRIMARY KEY, project_id TEXT, classification TEXT, mtime_ns INTEGER, bytes INTEGER, content TEXT)')
    try:db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(path,project_id,classification,content,content="docs",content_rowid="rowid")')
    except sqlite3.OperationalError:pass
    return db
def index_file(path:Path,*,project_id:str='',classification:str='',max_bytes:int=1024*1024)->dict[str,Any]:
    path=path.resolve();st=path.stat()
    if path.suffix.casefold() not in TEXT_SUFFIXES:return {'indexed':False,'reason':'non-text'}
    if st.st_size>max_bytes:return {'indexed':False,'reason':'too-large'}
    content=path.read_text(encoding='utf-8',errors='replace')
    db=_connect()
    try:
        db.execute('INSERT OR REPLACE INTO docs(path,project_id,classification,mtime_ns,bytes,content) VALUES(?,?,?,?,?,?)',(str(path),project_id,classification,st.st_mtime_ns,st.st_size,content));db.commit()
        try:
            rowid=db.execute('SELECT rowid FROM docs WHERE path=?',(str(path),)).fetchone()[0]
            db.execute('INSERT OR REPLACE INTO docs_fts(rowid,path,project_id,classification,content) VALUES(?,?,?,?,?)',(rowid,str(path),project_id,classification,content));db.commit()
        except sqlite3.OperationalError:pass
    finally:db.close()
    return {'indexed':True,'path':str(path),'bytes':st.st_size}
def search(query:str,limit:int=100)->list[dict[str,Any]]:
    db=_connect()
    try:
        try:rows=db.execute('SELECT path,project_id,classification,snippet(docs_fts,3,"[","]","…",12) FROM docs_fts WHERE docs_fts MATCH ? LIMIT ?',(query,max(1,int(limit)))).fetchall()
        except sqlite3.OperationalError:rows=db.execute('SELECT path,project_id,classification,substr(content,1,240) FROM docs WHERE content LIKE ? LIMIT ?',('%'+query+'%',max(1,int(limit)))).fetchall()
        return [{'path':r[0],'projectId':r[1],'classification':r[2],'snippet':r[3]} for r in rows]
    finally:db.close()
