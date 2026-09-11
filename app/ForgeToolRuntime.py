#!/usr/bin/env python3
from __future__ import annotations
import os, subprocess, threading, time
from pathlib import Path
from typing import Any, Callable

from ForgeActivity import append as activity_append
from ForgeReceipts import write as receipt_write
from ForgeToolContracts import ToolContract, validate_values, resolved_values
from ForgeToolRegistry import ToolSpec
from ForgeVersionConstraints import satisfies
from ForgeToolOutput import capture as capture_outputs

TOOL_RUNTIME_VERSION="FORGEPY-TOOL-RUNTIME-1.0"

def _argv(tool:ToolSpec, values:dict[str,Any], extra_args:list[str]|None=None) -> list[str]:
    if tool.kind == "declared-command":
        return []
    target=Path(tool.root)/tool.path
    argv=[]
    if tool.interpreter: argv.append(tool.interpreter)
    argv.append(str(target))
    for arg in tool.args:
        rendered=str(arg)
        for key,value in values.items():
            rendered=rendered.replace("{"+key+"}",str(value))
        argv.append(rendered)
    argv.extend(extra_args or [])
    return argv

def execute(tool:ToolSpec, *, contract:ToolContract|None=None, values:dict[str,Any]|None=None,
            emit:Callable[[str],None]|None=None, cancel:threading.Event|None=None, extra_args:list[str]|None=None)->dict[str,Any]:
    values=values or {}; emit=emit or (lambda _line:None); root=Path(tool.root).resolve()
    if tool.state not in {'READY','EXECUTABLE','VERIFIED'}:
        raise RuntimeError(tool.reason or f'{tool.name} is not executable ({tool.state})')
    if contract:
        errors=validate_values(contract,values,project_root=root)
        if errors: raise ValueError('; '.join(errors))
        values=resolved_values(contract,values)
        timeout=max(1,int(contract.policy.timeout_seconds))
        max_output=max(4096,int(contract.policy.max_output_bytes))
    else:
        timeout=max(1,int(tool.timeout_seconds or 300)); max_output=8*1024*1024

    # When probe metadata exposes a version, enforce the declared requirement before execution.
    if contract and contract.version_requirement:
        probed=str((tool.probe or {}).get('version') or (tool.probe or {}).get('detectedVersion') or '')
        if probed and not satisfies(probed,contract.version_requirement):
            raise RuntimeError(f'tool version {probed} does not satisfy {contract.version_requirement}')
    activity_append("tool.started",tool.project_id,toolId=tool.tool_id,capability=tool.capability)
    started=time.monotonic()
    if tool.kind=="declared-command":
        from PCCSurfaceCommon import ProjectContract, BackendClient
        backend=BackendClient(root,ProjectContract.load(root))
        if not backend.supports(tool.capability): raise RuntimeError(f'Project command unavailable: {tool.capability}')
        proc=backend.popen(tool.capability)
    else:
        proc=subprocess.Popen(_argv(tool,values,extra_args),cwd=tool.working_directory or tool.root,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',
            env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'},
            creationflags=int(getattr(subprocess,'CREATE_NO_WINDOW',0)) if os.name=='nt' else 0)

    chunks=[]; size=0; timed_out=False; cancelled=False
    try:
        while True:
            if cancel is not None and cancel.is_set():
                cancelled=True; proc.terminate()
            if time.monotonic()-started>timeout:
                timed_out=True; proc.terminate()
            line=proc.stdout.readline() if proc.stdout else ''
            if line:
                emit(line)
                encoded=line.encode('utf-8',errors='replace')
                if size < max_output:
                    remain=max_output-size; chunks.append(encoded[:remain].decode('utf-8',errors='replace')); size+=min(len(encoded),remain)
            if proc.poll() is not None: break
            if timed_out or cancelled:
                try: proc.wait(timeout=2)
                except Exception: proc.kill()
                break
            if not line: time.sleep(.02)
        rc=int(proc.wait() if proc.poll() is None else proc.returncode or 0)
    finally:
        if proc.poll() is None: proc.kill()
    elapsed=round((time.monotonic()-started)*1000,1)
    result={'toolId':tool.tool_id,'capability':tool.capability,'returncode':rc,'elapsedMs':elapsed,
            'cancelled':cancelled,'timedOut':timed_out,'output':''.join(chunks),'values':values,
            'artifacts':capture_outputs(contract,root) if contract else []}
    receipt=receipt_write(tool.project_id,'tools',result)
    result['receipt']=str(receipt)
    activity_append("tool.finished",tool.project_id,toolId=tool.tool_id,returncode=rc,elapsedMs=elapsed,receipt=str(receipt))
    return result
