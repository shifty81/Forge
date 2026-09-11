#!/usr/bin/env python3
from __future__ import annotations
import time
from typing import Any,Callable
TREE_CACHE_VERSION='FORGEPY-REPO-TREE-CACHE-1.0'
class RepoTreeCache:
    def __init__(self)->None:self._rows=[];self._stamp=0.;self._key=''
    def get(self,key:str,ttl:float,loader:Callable[[],list[dict[str,Any]]]):
        now=time.monotonic()
        if key==self._key and now-self._stamp<=ttl:return list(self._rows)
        self._rows=list(loader());self._key=key;self._stamp=now;return list(self._rows)
    def invalidate(self):self._stamp=0.;self._key='';self._rows=[]
