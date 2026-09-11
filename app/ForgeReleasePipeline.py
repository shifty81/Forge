#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from ForgeReleaseModel import manifest as release_manifest

RELEASE_PIPELINE_VERSION="FORGEPY-RELEASE-PIPELINE-1.0"

def offline_bundle(version:str,build:str,files:list[Path],destination:Path,channel:str='preview')->dict[str,Any]:
    data=release_manifest(version,build,files,channel)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:
            if p.is_file(): z.write(p,p.name)
        z.writestr('FORGEPY_RELEASE_MANIFEST.json',json.dumps(data,indent=2,sort_keys=True)+'\n')
    return {'path':str(destination),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'manifest':data}

def signing_readiness(*, certificate_configured:bool, artifact_exists:bool, hashes_verified:bool)->dict[str,Any]:
    checks={'certificateConfigured':bool(certificate_configured),'artifactExists':bool(artifact_exists),'hashesVerified':bool(hashes_verified)}
    return {'ready':all(checks.values()),'checks':checks,'note':'ForgePY never fabricates a signature; Windows signing must use operator-owned credentials.'}
