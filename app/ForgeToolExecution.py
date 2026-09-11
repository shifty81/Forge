#!/usr/bin/env python3
from __future__ import annotations
import os, subprocess, threading, time
from pathlib import Path
from typing import Any, Callable
from ForgeToolContracts import ToolContract, validate_values
EXECUTION_VERSION='FORGEPY-TOOL-EXECUTION-1.0'
class ToolExecutionError(RuntimeError):pass
def run(argv:list[str], *, contract:ToolContract|None=None, values:dict[str,Any]|None=None, cwd:Path|str|None=None, emit:Callable[[str],None]|None=None, cancel:threading.Event|None=None)->dict[str,Any]:
    if contract:
        errors=validate_values(contract,values or {})
        if errors:raise ToolExecutionError('; '.join(errors))
        timeout=max(1,int(contract.policy.timeout_seconds))
    else:timeout=300
    emit=emit or (lambda _x:None); started=time.monotonic(); proc=subprocess.Popen(argv,cwd=str(cwd) if cwd else None,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
    output=[]
    try:
        while True:
            if cancel is not None and cancel.is_set(): proc.terminate(); raise ToolExecutionError('cancelled')
            if time.monotonic()-started>timeout: proc.terminate(); raise ToolExecutionError(f'timeout after {timeout}s')
            line=proc.stdout.readline() if proc.stdout else ''
            if line:output.append(line); emit(line)
            if proc.poll() is not None:
                if proc.stdout:
                    tail=proc.stdout.read()
                    if tail:output.append(tail); emit(tail)
                break
            if not line:time.sleep(.02)
    finally:
        if proc.poll() is None:proc.kill()
    return {'returncode':int(proc.returncode or 0),'elapsedMs':round((time.monotonic()-started)*1000,1),'output':''.join(output)}
