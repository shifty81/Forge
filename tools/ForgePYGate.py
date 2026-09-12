#!/usr/bin/env python3
"""Canonical ForgePY quality-gate entrypoint."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from ForgeGate import *  # noqa: F401,F403
from ForgeGate import main


def _refresh_manifest_for_full() -> int:
    if "full" not in {str(arg).casefold() for arg in sys.argv[1:]}:
        return 0
    root=Path(__file__).resolve().parents[1]
    cp=subprocess.run([sys.executable,str(root/"tools"/"BuildForgePYManifest.py")],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False)
    if cp.stdout: print(cp.stdout,end="")
    return int(cp.returncode)


if __name__ == "__main__":
    rc=_refresh_manifest_for_full()
    raise SystemExit(rc if rc else main())
