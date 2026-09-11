#!/usr/bin/env python3
from __future__ import annotations
import os,platform,sys
from pathlib import Path
from typing import Any
from ForgePYVersion import VERSION,BUILD
from ForgeToolchainDoctor import inspect as inspect_toolchain
from ForgeSecurity import redact_text
DIAGNOSTICS_VERSION='FORGEPY-DIAGNOSTICS-2.0'
def snapshot(project_root:Path|None=None)->dict[str,Any]:
    return {'schema':'forgepy.diagnostics.v2','version':DIAGNOSTICS_VERSION,'forgepy':{'version':VERSION,'build':BUILD},'python':sys.version.split()[0],'platform':platform.platform(),'cwd':str(Path.cwd()),'projectRoot':str(project_root) if project_root else '', 'toolchain':inspect_toolchain()}
