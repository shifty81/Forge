#!/usr/bin/env python3
from __future__ import annotations
import hashlib,shutil
from pathlib import Path
from typing import Any
from ForgeSelfUpdatePlan import UpdatePlan
SELF_UPDATE_RUNTIME_VERSION='FORGEPY-SELF-UPDATE-RUNTIME-1.0'
def sha256(path:Path)->str:
    h=hashlib.sha256();
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def stage(plan:UpdatePlan,expected_sha256:str)->dict[str,Any]:
    source=Path(plan.source);staged=Path(plan.staged);staged.parent.mkdir(parents=True,exist_ok=True)
    if sha256(source)!=expected_sha256:raise RuntimeError('update hash mismatch')
    shutil.copy2(source,staged)
    if sha256(staged)!=expected_sha256:raise RuntimeError('staged update verification failed')
    plan.state='STAGED';return {'ok':True,'state':plan.state,'staged':str(staged),'sha256':expected_sha256}
def promotion_plan(plan:UpdatePlan)->dict[str,Any]:
    return {'schema':'forgepy.self-update-promotion.v1','version':SELF_UPDATE_RUNTIME_VERSION,'current':plan.current,'staged':plan.staged,'rollback':plan.rollback,'steps':['wait-for-exit','backup-current','promote-staged','restart','self-test','certify-or-rollback'],'automatic':False}
