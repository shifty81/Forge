#!/usr/bin/env python3
from __future__ import annotations
import json,os,subprocess,sys
from pathlib import Path
from typing import Any
PLUGIN_HOST_VERSION='FORGEPY-PLUGIN-HOST-1.0'
def invoke(entrypoint:Path,payload:dict[str,Any],*,timeout:int=60)->dict[str,Any]:
    if not entrypoint.is_file():return {'ok':False,'error':'entrypoint missing'}
    code='import json,runpy,sys; ns=runpy.run_path(sys.argv[1]); fn=ns.get("forgepy_invoke"); data=json.loads(sys.stdin.read()); print(json.dumps(fn(data) if callable(fn) else {"error":"forgepy_invoke missing"},default=str))'
    cp=subprocess.run([sys.executable,'-I','-c',code,str(entrypoint)],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=max(1,int(timeout)),env={k:v for k,v in os.environ.items() if k in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP'}})
    if cp.returncode!=0:return {'ok':False,'error':cp.stderr.strip(),'returncode':cp.returncode}
    try:return {'ok':True,'result':json.loads(cp.stdout)}
    except Exception:return {'ok':True,'result':cp.stdout.strip()}
