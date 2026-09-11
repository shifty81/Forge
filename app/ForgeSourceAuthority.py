#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
SOURCE_AUTHORITY_VERSION="FORGEPY-SOURCE-AUTHORITY-1.0"

def matrix(*, working:str='', head:str='', green:str='', forgegit:str='', github:str='')->dict[str,Any]:
    refs={'working':working,'head':head,'green':green,'forgegit':forgegit,'github':github}
    present={k:v for k,v in refs.items() if v}
    unique=set(present.values())
    if not present: state='UNKNOWN'
    elif len(unique)==1: state='SYNC'
    else: state='DIVERGED'
    return {'version':SOURCE_AUTHORITY_VERSION,'state':state,'refs':refs,'distinct':len(unique)}

def safe_branch_name(name:str)->str:
    value='-'.join(str(name).strip().split())
    for bad in ('..','~','^',':','?','*','[','\\',' '): value=value.replace(bad,'-')
    value=value.strip('/.-')
    if not value: raise ValueError('branch name is empty')
    return value
