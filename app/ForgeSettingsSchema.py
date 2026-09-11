#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
SETTINGS_SCHEMA_VERSION='FORGEPY-SETTINGS-SCHEMA-3.0'
KNOWN_TOP={'schema','version','vaultHome','projectsRoot','scanRoots','artifactCentralRoot','portable','ui','services','intake','forgejo','sourceControl','ide','cortex','tooling','security','plugins','automation','retention','release'}
def validate(data:dict[str,Any])->list[str]:
    errors=[]
    if not isinstance(data,dict):return ['settings must be an object']
    for key in ('vaultHome','projectsRoot','artifactCentralRoot'):
        if key in data and not isinstance(data[key],str):errors.append(f'{key} must be a string')
    if 'scanRoots' in data and not isinstance(data['scanRoots'],list):errors.append('scanRoots must be a list')
    ui=data.get('ui') or {}
    if ui and not isinstance(ui,dict):errors.append('ui must be an object')
    if isinstance(ui,dict):
        ratio=ui.get('workspaceConsoleRatio')
        if ratio is not None:
            try:
                if not (0.20<=float(ratio)<=0.70):errors.append('ui.workspaceConsoleRatio must be between 0.20 and 0.70')
            except Exception:errors.append('ui.workspaceConsoleRatio must be numeric')
        threads=ui.get('workerThreads')
        if threads is not None:
            try:
                if not (2<=int(threads)<=32):errors.append('ui.workerThreads must be between 2 and 32')
            except Exception:errors.append('ui.workerThreads must be an integer')
    intake=data.get('intake') or {}
    if isinstance(intake,dict) and intake.get('archiveNonPatchArtifacts',False):
        errors.append('intake.archiveNonPatchArtifacts must remain false; automatic non-patch movement is forbidden')
    plugins=data.get('plugins') or {}
    if plugins and not isinstance(plugins,dict):errors.append('plugins must be an object')
    return errors
def unknown_keys(data:dict[str,Any])->list[str]:return sorted(set(data)-KNOWN_TOP)
