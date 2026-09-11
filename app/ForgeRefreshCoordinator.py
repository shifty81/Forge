#!/usr/bin/env python3
from __future__ import annotations
import threading,time
from typing import Any
REFRESH_VERSION='FORGEPY-REFRESH-1.0'
class RefreshCoordinator:
    def __init__(self)->None:
        self._lock=threading.RLock(); self._last:dict[str,float]={}; self._busy:set[str]=set()
    def should_refresh(self,key:str,debounce_ms:int=350)->bool:
        now=time.monotonic()
        with self._lock:
            if key in self._busy:return False
            return (now-self._last.get(key,0.0))*1000.0>=max(0,int(debounce_ms))
    def begin(self,key:str,debounce_ms:int=350)->bool:
        if not self.should_refresh(key,debounce_ms):return False
        with self._lock:self._busy.add(key)
        return True
    def finish(self,key:str)->None:
        with self._lock:self._busy.discard(key); self._last[key]=time.monotonic()
    def busy(self,key:str)->bool:
        with self._lock:return key in self._busy
