#!/usr/bin/env python3
from __future__ import annotations
import os,subprocess,time
from pathlib import Path
from typing import Any,Sequence
PROBE_VERSION='FORGEPY-TOOL-PROBE-1.1'; SAFE_FLAGS=(('--version',),('-V',),('--help',),('-h',))
def _creationflags()->int:return int(getattr(subprocess,'CREATE_NO_WINDOW',0)) if os.name=='nt' else 0
def _startupinfo():
    if os.name!='nt':return None
    info=subprocess.STARTUPINFO(); info.dwFlags|=int(getattr(subprocess,'STARTF_USESHOWWINDOW',1)); info.wShowWindow=int(getattr(subprocess,'SW_HIDE',0)); return info
def probe_command(argv:Sequence[str],*,cwd:Path|str|None=None,timeout:float=4.0)->dict[str,Any]:
    base=[str(x) for x in argv if str(x)]
    if not base:return {'ok':False,'program':'','attempts':[],'error':'empty probe command'}
    attempts=[]
    for flags in SAFE_FLAGS:
        started=time.monotonic()
        try:
            cp=subprocess.run([*base,*flags],cwd=str(cwd) if cwd else None,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=max(.5,float(timeout)),env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'},creationflags=_creationflags(),startupinfo=_startupinfo())
            text=((cp.stdout or '')+'\n'+(cp.stderr or '')).strip()[:16000]; row={'args':[*base,*flags],'returncode':cp.returncode,'elapsedMs':round((time.monotonic()-started)*1000,1),'output':text}; attempts.append(row)
            if text:return {'ok':True,'program':base[0],'selected':row,'attempts':attempts}
        except (OSError,subprocess.SubprocessError) as exc:attempts.append({'args':[*base,*flags],'error':str(exc)})
    return {'ok':False,'program':base[0],'attempts':attempts}
def probe(program:str,*,cwd:Path|str|None=None,timeout:float=4.0)->dict[str,Any]:return probe_command([program],cwd=cwd,timeout=timeout)
