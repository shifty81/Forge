#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
HEALTH_V3_VERSION='FORGEPY-HEALTH-3.0'
def aggregate(checks:dict[str,Any])->dict[str,Any]:
    states=[]
    for k,v in checks.items():
        if isinstance(v,dict):state=str(v.get('state') or ('PASS' if v.get('ok') else 'FAIL')).upper()
        else:state=str(v).upper()
        states.append((k,state))
    overall='FAIL' if any(s=='FAIL' for _,s in states) else ('WARN' if any(s in {'WARN','UNKNOWN','BLOCKED'} for _,s in states) else 'PASS')
    return {'schema':'forgepy.health.v3','version':HEALTH_V3_VERSION,'overall':overall,'checks':dict(states)}
