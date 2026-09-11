#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
CONFLICT_VERSION='FORGEPY-GIT-CONFLICT-1.0'
def parse_porcelain(lines:str)->list[dict[str,Any]]:
    rows=[]
    for line in str(lines).splitlines():
        if len(line)<3:continue
        code=line[:2];path=line[3:].strip()
        if code in {'UU','AA','DD','AU','UA','DU','UD'}:rows.append({'code':code,'path':path,'state':'CONFLICT'})
    return rows
def resolution_plan(path:str,choice:str)->dict[str,Any]:
    if choice not in {'ours','theirs','manual'}:raise ValueError('choice must be ours, theirs or manual')
    commands=[] if choice=='manual' else [['git','checkout',f'--{choice}','--',path],['git','add','--',path]]
    return {'schema':'forgepy.git-conflict-plan.v1','version':CONFLICT_VERSION,'path':path,'choice':choice,'commands':commands,'automatic':False}
