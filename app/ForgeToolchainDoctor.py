#!/usr/bin/env python3
from __future__ import annotations
import os, shutil, sys
from typing import Any

DOCTOR_VERSION='FORGEPY-TOOLCHAIN-DOCTOR-2.0'
TOOLS={
 'git':(['git'], 'Git.Git'), 'github':(['gh'], 'GitHub.cli'), 'python':([sys.executable], ''),
 'cargo':(['cargo'], 'Rustlang.Rustup'), 'cmake':(['cmake'], 'Kitware.CMake'), 'ninja':(['ninja'], 'Ninja-build.Ninja'),
 'node':(['node'], 'OpenJS.NodeJS.LTS'), 'dotnet':(['dotnet'], 'Microsoft.DotNet.SDK.8'),
 'blender':(['blender'], 'BlenderFoundation.Blender'), 'java':(['java'], 'EclipseAdoptium.Temurin.21.JDK'), 'msbuild':(['msbuild'], 'Microsoft.VisualStudio.2022.BuildTools'),
}
def _find(candidates):
    for c in candidates:
        if os.path.isabs(str(c)) and os.path.isfile(str(c)): return str(c)
        found=shutil.which(str(c))
        if found:return found
    return ''
def inspect()->dict[str,Any]:
    rows=[]
    for name,(cands,winget) in TOOLS.items():
        found=_find(cands); rows.append({'tool':name,'ready':bool(found),'path':found,'wingetId':winget,'installable':bool(winget)})
    return {'schema':'forgepy.toolchain-doctor.v1','rows':rows,'ready':sum(r['ready'] for r in rows),'missing':sum(not r['ready'] for r in rows)}
def bootstrap_plan()->list[dict[str,str]]:
    return [{'tool':r['tool'],'command':f'winget install --id {r["wingetId"]} --exact'} for r in inspect()['rows'] if not r['ready'] and r['wingetId']]
