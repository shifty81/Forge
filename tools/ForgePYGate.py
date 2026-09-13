#!/usr/bin/env python3
"""Canonical ForgePY quality-gate entrypoint."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path
from ForgeGate import *  # noqa: F401,F403
from ForgeGate import main


def _source_authority_check_for_full() -> int:
    if "full" not in {str(arg).casefold() for arg in sys.argv[1:]}:
        return 0
    root = Path(__file__).resolve().parents[1]
    authority_script = root / "app" / "ForgeSourceAuthority.py"
    try:
        cp = subprocess.run(
            [sys.executable, str(authority_script), "--root", str(root)],
            cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("[FAIL] ForgePY source-authority preflight timed out after 120s.", flush=True)
        return 1
    if cp.stdout:
        print(cp.stdout, end="")
    return int(cp.returncode)

def _refresh_manifest_for_full() -> int:
    if "full" not in {str(arg).casefold() for arg in sys.argv[1:]}:
        return 0
    root = Path(__file__).resolve().parents[1]
    try:
        cp = subprocess.run(
            [sys.executable, str(root / "tools" / "BuildForgePYManifest.py")],
            cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("[FAIL] ForgePY package-manifest refresh timed out after 300s.", flush=True)
        return 1
    if cp.stdout:
        print(cp.stdout, end="")
    return int(cp.returncode)

if __name__ == "__main__":
    rc = _source_authority_check_for_full()
    if not rc:
        rc = _refresh_manifest_for_full()
    raise SystemExit(rc if rc else main())
