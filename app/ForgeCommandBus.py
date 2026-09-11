#!/usr/bin/env python3
from __future__ import annotations
import threading
from dataclasses import dataclass
from typing import Any, Callable

COMMAND_BUS_VERSION='FORGEPY-COMMAND-BUS-2.0'

@dataclass(frozen=True)
class CommandSpec:
    key: str
    handler: Callable[..., Any]
    category: str = ""
    mutates: bool = False
    description: str = ""
    owner: str = "forgepy"

@dataclass(frozen=True)
class CommandResult:
    key:str; ok:bool; value:Any=None; error:str=''

class CommandBus:
    def __init__(self)->None:
        self._handlers:dict[str,CommandSpec]={}
        self._lock=threading.RLock()

    def register(self,key:str,handler:Callable[...,Any],*,replace:bool=False,category:str="",mutates:bool=False,description:str="",owner:str="forgepy")->None:
        with self._lock:
            if key in self._handlers and not replace: raise KeyError(key)
            self._handlers[key]=CommandSpec(key,handler,category,bool(mutates),description,owner)

    def unregister(self,key:str)->bool:
        with self._lock: return self._handlers.pop(key,None) is not None

    def keys(self)->tuple[str,...]:
        with self._lock:return tuple(sorted(self._handlers))

    def specs(self)->tuple[CommandSpec,...]:
        with self._lock:return tuple(self._handlers[k] for k in sorted(self._handlers))

    def execute(self,key:str,*args,**kwargs)->CommandResult:
        with self._lock: spec=self._handlers.get(key)
        if spec is None:return CommandResult(key,False,error='command not registered')
        try:return CommandResult(key,True,value=spec.handler(*args,**kwargs))
        except Exception as exc:return CommandResult(key,False,error=str(exc))
