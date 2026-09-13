#!/usr/bin/env python3
from __future__ import annotations
import os, shutil, uuid
from pathlib import Path
from typing import Any
from ForgeInstallLayout import ensure, resolve

INSTALLER_VERSION="FORGEPY-INSTALLER-RUNTIME-1.0-F700"

def choices()->list[dict[str,str]]:
    return [
        {"mode":"installed","label":"Standard install","detail":"Application files in a per-user program folder; mutable ForgePY state in AppData."},
        {"mode":"portable","label":"Portable install","detail":"ForgePY.exe, companion files and Data stay together in the selected folder."},
    ]

def default_destination(mode:str)->Path:
    if mode.casefold()=="portable":
        return Path.home()/"ForgePY-Portable"
    local=Path(os.environ.get("LOCALAPPDATA") or (Path.home()/"AppData/Local"))
    return local/"Programs"/"ForgePY"

def plan(source:Path,mode:str,destination:Path|None=None)->dict[str,Any]:
    source=source.expanduser().resolve()
    destination=(destination or default_destination(mode)).expanduser().resolve()
    return {"schema":"forgepy.install-plan.v1","version":INSTALLER_VERSION,"source":str(source),"destination":str(destination),"mode":mode,"layout":resolve(destination,mode),"transactional":True}

def install(source:Path,mode:str,destination:Path|None=None,*,approved:bool=False)->dict[str,Any]:
    if not approved:
        raise PermissionError("ForgePY install requires explicit approval")
    p=plan(source,mode,destination)
    src=Path(p["source"]); dst=Path(p["destination"])
    if not src.is_dir():
        raise FileNotFoundError(src)
    incoming=dst.with_name(dst.name+f".incoming-{uuid.uuid4().hex[:8]}")
    rollback=dst.with_name(dst.name+".rollback")
    shutil.copytree(src,incoming)
    if not (incoming/"ForgePY.exe").is_file():
        shutil.rmtree(incoming,ignore_errors=True)
        raise RuntimeError("install image does not contain ForgePY.exe")
    if rollback.exists():
        shutil.rmtree(rollback,ignore_errors=True)
    if dst.exists():
        os.replace(dst,rollback)
    os.replace(incoming,dst)
    layout=ensure(resolve(dst,mode))
    return {"ok":True,"destination":str(dst),"rollback":str(rollback) if rollback.exists() else "","layout":layout}


def distribution_plan(source:Path)->dict[str,Any]:
    """Describe the two installer choices presented by the future installer UI."""
    source=source.expanduser().resolve()
    return {
        "schema":"forgepy.distribution-plan.v1",
        "version":INSTALLER_VERSION,
        "source":str(source),
        "choices":[
            {
                "mode":"installed",
                "destination":str(default_destination("installed")),
                "data":"%LOCALAPPDATA%\\ForgePY",
                "config":"%APPDATA%\\ForgePY",
                "updates":"AppData ForgePY update lane",
            },
            {
                "mode":"portable",
                "destination":str(default_destination("portable")),
                "data":"<install>\\Data",
                "config":"<install>\\Data\\Config",
                "updates":"<install>\\Data\\Updates",
            },
        ],
        "applicationUpdatesSeparateFromProjectUpdates":True,
        "inPlaceExePatching":False,
    }
