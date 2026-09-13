#!/usr/bin/env python3
from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Any

LAYOUT_VERSION="FORGEPY-INSTALL-LAYOUT-1.0-F700"

def _local()->Path:
    return Path(os.environ.get("LOCALAPPDATA") or (Path.home()/"AppData/Local"))
def _roaming()->Path:
    return Path(os.environ.get("APPDATA") or (Path.home()/"AppData/Roaming"))

def application_root()->Path:
    """Resolve the ForgePY application image, never the currently selected project."""
    executable = Path(sys.executable).expanduser().resolve()
    if executable.name.casefold() == "forgepy.exe":
        return executable.parent
    return Path(__file__).resolve().parents[1]

def resolve(app_root:Path|None=None,mode:str|None=None)->dict[str,Any]:
    root=(app_root or application_root()).expanduser().resolve()
    selected=(mode or ("portable" if (root/".forgepy-portable").exists() else "installed")).casefold()
    if selected=="portable":
        data=root/"Data"; config=data/"Config"
    else:
        data=_local()/"ForgePY"; config=_roaming()/"ForgePY"
    return {
        "schema":"forgepy.install-layout.v1","version":LAYOUT_VERSION,"mode":selected,
        "appRoot":str(root),"dataRoot":str(data),"configRoot":str(config),
        "updatesRoot":str(data/"Updates"),"rollbackRoot":str(data/"Rollback"),
        "logsRoot":str(data/"Logs"),"cacheRoot":str(data/"Cache"),
        "portableMarker":str(root/".forgepy-portable"),
    }

def ensure(layout:dict[str,Any])->dict[str,Any]:
    for key in ("dataRoot","configRoot","updatesRoot","rollbackRoot","logsRoot","cacheRoot"):
        Path(layout[key]).mkdir(parents=True,exist_ok=True)
    if layout.get("mode")=="portable":
        Path(layout["portableMarker"]).write_text("ForgePY portable install\n",encoding="utf-8")
    return layout
