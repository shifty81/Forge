#!/usr/bin/env python3
from __future__ import annotations
from collections import deque
import re, threading
CONSOLE_BUFFER_VERSION='FORGEPY-CONSOLE-BUFFER-1.0'
class ConsoleBuffer:
    def __init__(self,max_lines:int=30000)->None:self._lines=deque(maxlen=max(1000,int(max_lines))); self._lock=threading.RLock()
    def append(self,text:str)->int:
        rows=str(text).splitlines(True)
        with self._lock:self._lines.extend(rows)
        return len(rows)
    def tail(self,limit:int=500)->str:
        with self._lock:return ''.join(list(self._lines)[-max(1,int(limit)):])
    def search(self,query:str,limit:int=500)->list[str]:
        q=query.casefold()
        with self._lock:return [x for x in self._lines if q in x.casefold()][-max(1,int(limit)):]
    def clear(self)->None:
        with self._lock:self._lines.clear()
    def __len__(self)->int:
        with self._lock:return len(self._lines)
