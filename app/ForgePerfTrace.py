#!/usr/bin/env python3
from __future__ import annotations
import threading,time
from contextlib import contextmanager
from typing import Any
PERF_TRACE_VERSION='FORGEPY-PERF-TRACE-1.0'
class PerfTrace:
    def __init__(self,limit:int=1000):self.limit=max(10,limit);self._lock=threading.RLock();self._rows=[]
    def add(self,key:str,elapsed_ms:float,metadata:dict[str,Any]|None=None):
        with self._lock:self._rows.append({'key':key,'elapsedMs':round(elapsed_ms,2),'metadata':metadata or {},'slow':elapsed_ms>=100});self._rows=self._rows[-self.limit:]
    @contextmanager
    def measure(self,key:str,metadata:dict[str,Any]|None=None):
        s=time.perf_counter()
        try:yield
        finally:self.add(key,(time.perf_counter()-s)*1000,metadata)
    def recent(self,limit:int=100):
        with self._lock:return list(self._rows[-max(1,limit):])
