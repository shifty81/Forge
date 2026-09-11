#!/usr/bin/env python3
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from typing import Callable
MIGRATION_VERSION='FORGEPY-MIGRATIONS-1.0'
@dataclass(frozen=True)
class Migration:version:int;name:str;apply:Callable[[sqlite3.Connection],None]
def ensure_table(db:sqlite3.Connection)->None:db.execute('CREATE TABLE IF NOT EXISTS forgepy_schema(version INTEGER PRIMARY KEY,name TEXT NOT NULL,applied_utc TEXT DEFAULT CURRENT_TIMESTAMP)')
def current(db:sqlite3.Connection)->int:
    ensure_table(db);row=db.execute('SELECT MAX(version) FROM forgepy_schema').fetchone();return int(row[0] or 0)
def apply_all(db:sqlite3.Connection,migrations:list[Migration])->list[int]:
    ensure_table(db);done=[];cur=current(db)
    for m in sorted(migrations,key=lambda x:x.version):
        if m.version<=cur:continue
        with db:m.apply(db);db.execute('INSERT INTO forgepy_schema(version,name) VALUES(?,?)',(m.version,m.name))
        done.append(m.version);cur=m.version
    return done
