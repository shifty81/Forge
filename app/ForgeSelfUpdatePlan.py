#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Any
UPDATE_PLAN_VERSION='FORGEPY-SELF-UPDATE-PLAN-1.0'
STATES=('DISCOVERED','VERIFIED','STAGED','WAITING_FOR_EXIT','PROMOTED','SELF_TEST','CERTIFIED','ROLLED_BACK','FAILED')
@dataclass
class UpdatePlan:
    source:str; staged:str; current:str; rollback:str; state:str='DISCOVERED'; target_version:str=''; target_build:str=''
    def to_dict(self)->dict[str,Any]:return {'schema':'forgepy.self-update-plan.v1','version':UPDATE_PLAN_VERSION,**asdict(self)}
def create(source:Path,current:Path,stage_root:Path,target_version:str='',target_build:str='')->UpdatePlan:
    staged=stage_root/'ForgePY.next.exe'; rollback=current.with_suffix(current.suffix+'.rollback')
    return UpdatePlan(str(source),str(staged),str(current),str(rollback),target_version=target_version,target_build=target_build)
