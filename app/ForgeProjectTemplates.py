#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
TEMPLATE_VERSION='FORGEPY-PROJECT-TEMPLATE-1.0'
@dataclass(frozen=True)
class ProjectTemplate:
    template_id:str; name:str; kind:str; files:tuple[str,...]=(); commands:tuple[str,...]=()
BUILTINS=(ProjectTemplate('python-app','Python Application','python-application',('project.control.json','README.md'),('gate.full','run.gui')),ProjectTemplate('rust-workspace','Rust Workspace','rust-workspace',('project.control.json','Cargo.toml'),('gate.full','build.native')),ProjectTemplate('native-cpp','Native C++','native-cpp',('project.control.json','CMakeLists.txt'),('gate.full','build.native')))
def catalog()->list[dict[str,Any]]:return [asdict(x) for x in BUILTINS]
def onboarding_plan(template_id:str,root:str)->dict[str,Any]:
    item=next((x for x in BUILTINS if x.template_id==template_id),None)
    if not item:raise KeyError(template_id)
    return {'schema':'forgepy.onboarding-plan.v1','template':asdict(item),'root':root,'writes':list(item.files),'execute':False}
