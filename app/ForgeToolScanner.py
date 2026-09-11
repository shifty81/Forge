#!/usr/bin/env python3
from __future__ import annotations
import hashlib, os, re, shutil, sys
from pathlib import Path
from typing import Any
from ForgeToolRegistry import ToolSpec, save
from ForgeCommandTaxonomy import category_for
from ForgeToolProbe import probe_command
from VaultTooling import scan_scripts, read_declared_commands, _domain

TOOL_SCANNER_VERSION='FORGEPY-TOOL-SCANNER-0.1'
CAPS=[
 ('gate.full',('full-gate','quality-gate','certify','full_quality')),
 ('test.run',('test','tests','unittest','pytest')),
 ('build.all',('build','compile','cmake')),
 ('run.app',('run','launch','start')),
 ('asset.validate',('asset','validate')),
 ('world.generate',('worldgen','generate-world','world_generate')),
 ('blender.run',('blender',)),
 ('package.release',('package','release','rollup','bundle')),
 ('diagnostics.doctor',('doctor','diagnostic','audit','verify')),
]

def _capability(path:str, domain:str)->str:
    key=(path+' '+domain).casefold().replace('_','-')
    for cap,tokens in CAPS:
        if any(t in key for t in tokens): return cap
    if domain=='validation': return 'validation.run'
    if domain=='build': return 'build.tool'
    if domain=='blender': return 'blender.run'
    return f'tool.{domain or "general"}'
def _category(cap:str)->str:
    return category_for(cap)
def _interpreter(path:Path)->tuple[str,str]:
    ext=path.suffix.casefold()
    if ext in {'.py','.pyw'}: return (sys.executable,'')
    if ext=='.ps1': return (shutil.which('pwsh') or shutil.which('powershell') or '', 'PowerShell missing')
    if ext in {'.cmd','.bat'}: return ('cmd.exe' if os.name=='nt' else '', 'Windows command processor required')
    if ext=='.sh': return (shutil.which('bash') or '', 'bash missing')
    if ext in {'.exe','.com'}: return ('','')
    return ('','unsupported executable type')
def activate(root:Path, project_id:str)->dict[str,Any]:
    root=root.resolve(); tools=[]; seen=set()
    # Project-declared commands are strongest and are represented as verified capabilities.
    for row in read_declared_commands(root):
        ident='declared:'+row['key']; seen.add(ident)
        tools.append(ToolSpec(ident,row['label'],project_id,str(root),'project.control.json',row['key'],str(row.get('category') or 'Project'), 'declared-command', state='VERIFIED',source='project.control.json',mutates=bool(row.get('mutates')),reason='Executed through project command authority'))
    for record in scan_scripts(root):
        rel=record.path; key='file:'+rel.casefold()
        if key in seen: continue
        seen.add(key); target=root/rel; interp,reason=_interpreter(target); cap=_capability(rel,record.domain)
        runnable=bool(interp or target.suffix.casefold() in {'.exe','.com'}); probe_result={}
        if runnable:
            ext=target.suffix.casefold()
            if ext in {'.py','.pyw'}: probe_argv=[interp,str(target)]
            elif ext=='.ps1': probe_argv=[interp,'-NoProfile','-File',str(target)]
            elif ext in {'.cmd','.bat'}: probe_argv=[interp,'/d','/c',str(target)]
            elif ext=='.sh': probe_argv=[interp,str(target)]
            else: probe_argv=[str(target)]
            probe_result=probe_command(probe_argv,cwd=root,timeout=2.0)
        state='READY' if runnable else 'BLOCKED'
        if runnable and probe_result.get('ok'): reason='Safe metadata probe completed'
        elif runnable: reason='Executable path verified; safe metadata probe returned no metadata'
        tools.append(ToolSpec(key,target.stem,project_id,str(root),rel,cap,_category(cap),record.kind,state=state,interpreter=interp,working_directory=str(root),source=record.source,reason=reason,probe=probe_result))
    save(project_id,tools)
    return {'projectId':project_id,'count':len(tools),'ready':sum(t.state in {'READY','EXECUTABLE','VERIFIED'} for t in tools),'blocked':sum(t.state=='BLOCKED' for t in tools),'tools':tools}
