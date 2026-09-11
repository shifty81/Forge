#!/usr/bin/env python3
from __future__ import annotations
import threading,time,uuid
from dataclasses import dataclass,field
from typing import Any,Callable
GUI_TASKS_VERSION='FORGEPY-GUI-TASKS-1.0'
@dataclass
class GuiTask:
    task_id:str; key:str; project_id:str=''; state:str='QUEUED'; created:float=field(default_factory=time.time); started:float=0.; finished:float=0.; error:str=''
class GuiTaskRegistry:
    def __init__(self)->None:self._lock=threading.RLock();self._tasks={};self._active_keys=set()
    def begin(self,key:str,project_id:str='')->GuiTask:
        with self._lock:
            if key in self._active_keys:raise RuntimeError(f'task already active: {key}')
            t=GuiTask(uuid.uuid4().hex,key,project_id,'RUNNING',started=time.time());self._tasks[t.task_id]=t;self._active_keys.add(key);return t
    def finish(self,task_id:str,error:str='')->None:
        with self._lock:
            t=self._tasks.get(task_id)
            if not t:return
            t.error=str(error or '');t.state='FAIL' if error else 'PASS';t.finished=time.time();self._active_keys.discard(t.key)
    def active(self,key:str)->bool:
        with self._lock:return key in self._active_keys
    def snapshot(self)->list[dict[str,Any]]:
        with self._lock:return [dict(vars(t)) for t in self._tasks.values()]
