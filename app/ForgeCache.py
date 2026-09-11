#!/usr/bin/env python3
from __future__ import annotations
import threading,time
from typing import Any,Callable
CACHE_VERSION='FORGEPY-CACHE-1.0'
class TtlCache:
    def __init__(self)->None:self._lock=threading.RLock();self._data={}
    def get(self,key:str,ttl:float,loader:Callable[[],Any])->Any:
        now=time.monotonic()
        with self._lock:
            row=self._data.get(key)
            if row and now-row[0] <= max(0,float(ttl)):return row[1]
        value=loader()
        with self._lock:self._data[key]=(now,value)
        return value
    def put(self,key:str,value:Any)->None:
        with self._lock:self._data[key]=(time.monotonic(),value)
    def invalidate(self,prefix:str='')->int:
        with self._lock:
            keys=[k for k in self._data if not prefix or k.startswith(prefix)]
            for k in keys:self._data.pop(k,None)
            return len(keys)
