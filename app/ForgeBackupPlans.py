#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
BACKUP_VERSION='FORGEPY-BACKUP-PLAN-1.0'
def project_plan(project_root:Path,destination:Path)->dict[str,Any]:
    return {'schema':'forgepy.backup-plan.v1','version':BACKUP_VERSION,'source':str(project_root.resolve()),'destination':str(destination.expanduser()),'include':['source-control','project.control.json','critical-config'],'exclude':['target','build','node_modules','.cache'],'execute':False}
