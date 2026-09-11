#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
TOOLCHAIN_PROVIDERS_VERSION='FORGEPY-TOOLCHAIN-PROVIDERS-1.0'
@dataclass(frozen=True)
class Provider:
    key:str; display:str; windows_hint:str=''; website:str=''; silent_install:bool=False
PROVIDERS={
'git':Provider('git','Git','winget install --id Git.Git -e'),
'gh':Provider('gh','GitHub CLI','winget install --id GitHub.cli -e'),
'rust':Provider('rust','Rust','winget install --id Rustlang.Rustup -e'),
'cmake':Provider('cmake','CMake','winget install --id Kitware.CMake -e'),
'ninja':Provider('ninja','Ninja','winget install --id Ninja-build.Ninja -e'),
'node':Provider('node','Node.js','winget install --id OpenJS.NodeJS.LTS -e'),
'dotnet':Provider('dotnet','.NET SDK','winget install --id Microsoft.DotNet.SDK.8 -e'),
'blender':Provider('blender','Blender','winget install --id BlenderFoundation.Blender -e'),}
def describe(key:str)->dict[str,Any]:
    p=PROVIDERS.get(key);return asdict(p) if p else {}
def approved_install_plan(key:str,approved:bool=False)->dict[str,Any]:
    p=PROVIDERS.get(key)
    if not p:return {'ready':False,'reason':'unknown toolchain'}
    return {'ready':bool(approved),'approved':bool(approved),'provider':asdict(p),'command':p.windows_hint if approved else '', 'automatic':False}
