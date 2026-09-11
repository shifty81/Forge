#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,platform,subprocess,sys
from typing import Any
FINGERPRINT_VERSION='FORGEPY-ENV-FINGERPRINT-1.0'
def capture()->dict[str,Any]:
    rows={'python':sys.version.split()[0],'platform':platform.platform(),'machine':platform.machine()}
    for tool in ('git','cmake','cargo','node','dotnet'):
        try:cp=subprocess.run([tool,'--version'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=2); rows[tool]=(cp.stdout or cp.stderr).strip().splitlines()[0][:200]
        except Exception:rows[tool]=''
    canonical=json.dumps(rows,sort_keys=True,separators=(',',':')).encode(); return {'schema':'forgepy.environment-fingerprint.v1','version':FINGERPRINT_VERSION,'values':rows,'sha256':hashlib.sha256(canonical).hexdigest()}
