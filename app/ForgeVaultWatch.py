#!/usr/bin/env python3
from __future__ import annotations
import os,time
from pathlib import Path
from typing import Callable,Any
WATCH_VERSION='FORGEPY-VAULT-WATCH-1.0'
def snapshot(root:Path,max_entries:int=200000)->dict[str,tuple[int,int]]:
    out={};count=0
    for base,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if d not in {'.git','node_modules','target','build','__pycache__'}]
        for name in files:
            p=Path(base)/name
            try:s=p.stat();out[str(p)]=(s.st_mtime_ns,s.st_size)
            except OSError:continue
            count+=1
            if count>=max_entries:return out
    return out
def diff(old:dict[str,tuple[int,int]],new:dict[str,tuple[int,int]])->dict[str,list[str]]:
    return {'added':sorted(set(new)-set(old)),'removed':sorted(set(old)-set(new)),'changed':sorted(k for k in set(old)&set(new) if old[k]!=new[k])}
def poll_once(root:Path,previous:dict[str,tuple[int,int]]|None=None)->tuple[dict[str,tuple[int,int]],dict[str,list[str]]]:
    cur=snapshot(root);return cur,diff(previous or {},cur)
