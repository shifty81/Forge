#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
NOTIFY_VERSION='FORGEPY-NOTIFY-1.0'
@dataclass(frozen=True)
class Notice:
    key:str; title:str; message:str; severity:str='info'; dedupe_key:str=''; actionable:bool=False
class NoticeCenter:
    def __init__(self):self._seen=set();self._rows=[]
    def publish(self,n:Notice)->bool:
        k=n.dedupe_key or n.key
        if k in self._seen:return False
        self._seen.add(k);self._rows.append(n);return True
    def rows(self)->list[dict[str,Any]]:return [asdict(x) for x in self._rows]
    def reset(self,key:str='')->None:
        if key:self._seen.discard(key)
        else:self._seen.clear()
