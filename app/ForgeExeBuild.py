#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from ForgeStandaloneBuild import command, expected_build_parent, portable_output, preflight

EXE_BUILD_VERSION = "FORGEPY-EXE-BUILD-3.0-F740"


def plan(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    info = preflight(root)
    return {
        "schema": "forgepy.exe-build-plan.v2",
        "version": EXE_BUILD_VERSION,
        "preflight": info,
        "command": command(root),
        "requiresWindows": True,
        "automatic": False,
        "packaging": "portable-onedir",
        "output": str(portable_output(root)),
        "entrypoint": str(root / "app" / "ForgePYBootstrap.py"),
        "selfUpdateReady": True,
    }


def _find_dist(build_parent: Path) -> Path:
    candidates = [path for path in build_parent.glob("*.dist") if path.is_dir() and (path / "ForgePY.exe").is_file()]
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one Nuitka standalone output containing ForgePY.exe, found {len(candidates)}")
    return candidates[0]


def execute(root: Path, *, approved: bool = False) -> dict[str, Any]:
    root = root.expanduser().resolve()
    build_plan = plan(root)
    if not approved:
        raise PermissionError("standalone build requires explicit approval")
    if not build_plan["preflight"].get("readyForWindowsBuild"):
        raise RuntimeError("Windows Nuitka preflight not ready")

    build_parent = expected_build_parent(root)
    if build_parent.exists():
        shutil.rmtree(build_parent)
    build_parent.mkdir(parents=True, exist_ok=True)
    build_command = command(root, build_root=build_parent)
    cp = subprocess.run(
        build_command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=14400,
        check=False,
    )
    if cp.returncode != 0:
        return {"ok": False, "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}

    built = _find_dist(build_parent)
    destination = portable_output(root)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(built), str(destination))
    exe = destination / "ForgePY.exe"
    return {
        "ok": exe.is_file(),
        "returncode": 0 if exe.is_file() else 1,
        "stdout": cp.stdout,
        "stderr": cp.stderr,
        "output": str(destination),
        "executable": str(exe),
        "packaging": "portable-onedir",
        "selfUpdateReady": True,
    }
