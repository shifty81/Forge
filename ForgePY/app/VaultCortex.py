#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from PCCSurfaceCommon import ProjectRegistry
from VaultSettings import load_settings


def find_cortex_root() -> Path | None:
    configured = str((load_settings().get("cortex") or {}).get("projectRoot") or "").strip()
    if configured and Path(configured).is_dir():
        return Path(configured).expanduser().resolve()
    try:
        for row in ProjectRegistry().entries():
            if row.name.casefold() == "cortex" or row.root.name.casefold() in {"cortex", "cortex-main"}:
                if row.root.is_dir():
                    return row.root.resolve()
    except Exception:
        pass
    return None


def status() -> dict[str, Any]:
    root = find_cortex_root()
    cfg = load_settings().get("cortex") or {}
    exe = str(cfg.get("executable") or "").strip()
    return {
        "root": str(root) if root else "",
        "registered": bool(root),
        "executable": exe,
        "executableReady": bool(exe and Path(exe).is_file()),
        "serviceUrl": str(cfg.get("serviceUrl") or ""),
    }


def start() -> subprocess.Popen[str] | None:
    cfg = load_settings().get("cortex") or {}
    root = find_cortex_root()
    exe = str(cfg.get("executable") or "").strip()
    args = [str(x) for x in (cfg.get("arguments") or [])]
    if exe and Path(exe).is_file():
        flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
        return subprocess.Popen([exe, *args], cwd=str(root or Path(exe).parent), creationflags=flags)
    if root:
        for candidate in (root / "Cortex.vbs", root / "Cortex.cmd", root / "PROJECT_CONTROL_CENTER.cmd"):
            if candidate.is_file():
                if candidate.suffix.casefold() == ".vbs" and os.name == "nt":
                    return subprocess.Popen(["wscript.exe", str(candidate)], cwd=str(root))
                if candidate.suffix.casefold() == ".cmd" and os.name == "nt":
                    return subprocess.Popen(["cmd.exe", "/c", str(candidate)], cwd=str(root))
    return None


__all__ = ["find_cortex_root", "start", "status"]
