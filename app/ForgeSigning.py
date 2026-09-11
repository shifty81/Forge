#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
SIGNING_VERSION='FORGEPY-SIGNING-1.0'
def signtool_plan(file:Path,certificate_thumbprint:str='',timestamp_url:str='http://timestamp.digicert.com')->dict[str,Any]:
    ready=bool(file.is_file() and certificate_thumbprint.strip())
    cmd=['signtool','sign','/sha1',certificate_thumbprint.strip(),'/fd','SHA256','/tr',timestamp_url,'/td','SHA256',str(file)] if ready else []
    return {'schema':'forgepy.signing-plan.v1','version':SIGNING_VERSION,'ready':ready,'command':cmd,'automatic':False,'requiresOperatorCredential':True}
