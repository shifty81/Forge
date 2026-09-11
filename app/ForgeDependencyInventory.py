#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any
INVENTORY_VERSION='FORGEPY-DEPENDENCY-INVENTORY-1.0'
def scan(root:Path)->dict[str,Any]:
    rows=[]
    req=root/'requirements.txt'
    if req.is_file():
        for line in req.read_text(encoding='utf-8',errors='replace').splitlines():
            line=line.strip()
            if line and not line.startswith('#'):rows.append({'ecosystem':'python','declaration':line,'source':'requirements.txt'})
    cargo=root/'Cargo.toml'
    if cargo.is_file():
        text=cargo.read_text(encoding='utf-8',errors='replace'); in_deps=False
        for line in text.splitlines():
            s=line.strip()
            if s.startswith('['):in_deps=s in {'[dependencies]','[dev-dependencies]','[build-dependencies]'};continue
            if in_deps and '=' in s and not s.startswith('#'):rows.append({'ecosystem':'cargo','declaration':s,'source':'Cargo.toml'})
    for csproj in root.glob('*.csproj'):
        rows.append({'ecosystem':'dotnet','declaration':csproj.name,'source':csproj.name})
    props=root/'Directory.Packages.props'
    if props.is_file(): rows.append({'ecosystem':'dotnet','declaration':'central-package-management','source':props.name})
    cmake=root/'CMakeLists.txt'
    if cmake.is_file(): rows.append({'ecosystem':'cmake','declaration':'CMakeLists.txt','source':'CMakeLists.txt'})
    for lock in ('Cargo.lock','package-lock.json','pnpm-lock.yaml','yarn.lock','requirements.lock','poetry.lock'):
        lp=root/lock
        if lp.is_file(): rows.append({'ecosystem':'lockfile','declaration':lock,'source':lock})
    package=root/'package.json'
    if package.is_file():
        try:data=json.loads(package.read_text(encoding='utf-8'))
        except Exception:data={}
        for section in ('dependencies','devDependencies'):
            for name,ver in (data.get(section) or {}).items():rows.append({'ecosystem':'npm','declaration':f'{name}@{ver}','source':'package.json'})
    return {'schema':'forgepy.dependencies.v1','version':INVENTORY_VERSION,'root':str(root),'rows':rows,'count':len(rows)}
