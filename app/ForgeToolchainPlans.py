#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
PLAN_VERSION='FORGEPY-TOOLCHAIN-PLAN-1.0'
def build(rows:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for row in rows:
        if row.get('ready'):continue
        item={'tool':row.get('tool'),'state':'MISSING','action':'locate-or-install','safeAutoInstall':False}
        if row.get('wingetId'):item['winget']=['winget','install','--id',row['wingetId'],'--exact']; item['availableInstaller']=True
        else:item['availableInstaller']=False
        out.append(item)
    return out
