#!/usr/bin/env python3
from __future__ import annotations
import threading,time
from dataclasses import dataclass,field
from typing import Any
STATE_BROKER_VERSION='FORGEPY-STATE-BROKER-1.0'
@dataclass
class ProjectState:
    project_id:str; generation:int=0; captured:float=0.0; values:dict[str,Any]=field(default_factory=dict)
class ProjectStateBroker:
    def __init__(self)->None:self._lock=threading.RLock(); self._states:dict[str,ProjectState]={}
    def snapshot(self,project_id:str)->ProjectState:
        with self._lock:
            s=self._states.get(project_id) or ProjectState(project_id)
            return ProjectState(s.project_id,s.generation,s.captured,dict(s.values))
    def update(self,project_id:str,**values:Any)->ProjectState:
        with self._lock:
            s=self._states.setdefault(project_id,ProjectState(project_id)); s.generation+=1; s.captured=time.time(); s.values.update(values)
            return self.snapshot(project_id)
    def invalidate(self,project_id:str,*keys:str)->None:
        with self._lock:
            s=self._states.setdefault(project_id,ProjectState(project_id)); s.generation+=1; s.captured=0.0
            if keys:
                for k in keys:s.values.pop(k,None)
            else:s.values.clear()
