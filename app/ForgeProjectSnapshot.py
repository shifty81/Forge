#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any
SNAPSHOT_VERSION='FORGEPY-PROJECT-SNAPSHOT-1.0'
@dataclass
class ProjectSnapshot:
    project_id:str; root:str; name:str=''; kind:str=''; branch:str=''; git_state:str='UNKNOWN'; green_state:str='UNKNOWN'; github_state:str='UNKNOWN'; forgegit_state:str='UNKNOWN'; pending_updates:int=0; tool_ready:int=0; tool_blocked:int=0; metadata:dict[str,Any]=field(default_factory=dict)
    def to_dict(self):return {'schema':'forgepy.project-snapshot.v1','version':SNAPSHOT_VERSION,**asdict(self)}
def merge(base:ProjectSnapshot,**changes:Any)->ProjectSnapshot:
    data=asdict(base);data.update(changes);return ProjectSnapshot(**data)
