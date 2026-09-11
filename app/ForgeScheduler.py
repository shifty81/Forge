#!/usr/bin/env python3
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any,Callable
SCHEDULER_VERSION='FORGEPY-SCHEDULER-1.0'
@dataclass
class Schedule:
    key:str; interval_seconds:int; enabled:bool=False; last_run:float=0.
def due(s:Schedule,now:float|None=None)->bool:
    now=time.time() if now is None else now
    return bool(s.enabled and s.interval_seconds>=60 and now-s.last_run>=s.interval_seconds)
def tick(schedules:list[Schedule],runner:Callable[[str],Any],*,global_enabled:bool=False,now:float|None=None)->list[str]:
    if not global_enabled:return []
    ran=[];now=time.time() if now is None else now
    for s in schedules:
        if due(s,now):runner(s.key);s.last_run=now;ran.append(s.key)
    return ran
