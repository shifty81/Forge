#!/usr/bin/env python3
from __future__ import annotations
import re
VERSION_CONSTRAINTS_VERSION='FORGEPY-VERSION-CONSTRAINTS-1.0'
def parse(v:str)->tuple[int,...]:
    nums=[int(x) for x in re.findall(r'\d+',str(v))[:4]]
    return tuple(nums or [0])
def _cmp(a,b):
    n=max(len(a),len(b));aa=a+(0,)*(n-len(a));bb=b+(0,)*(n-len(b));return (aa>bb)-(aa<bb)
def satisfies(version:str,requirement:str)->bool:
    req=str(requirement or '').strip()
    if not req:return True
    v=parse(version)
    for raw in [x.strip() for x in req.split(',') if x.strip()]:
        m=re.match(r'^(>=|<=|==|=|>|<|~)\s*(.+)$',raw)
        if not m:return False
        op,target=m.groups();t=parse(target);c=_cmp(v,t)
        if op in ('=','==') and c!=0:return False
        if op=='>' and c<=0:return False
        if op=='>=' and c<0:return False
        if op=='<' and c>=0:return False
        if op=='<=' and c>0:return False
        if op=='~' and (len(v)<2 or len(t)<2 or v[:2]!=t[:2] or c<0):return False
    return True
