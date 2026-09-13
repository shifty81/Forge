#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from typing import Any

BUILD_VERSION = "FORGEPY-STANDALONE-BUILD-4.0-F740"
NUMERIC_FILE_VERSION = "0.5.0.741"


def _nuitka_available() -> bool:
    return bool(shutil.which("nuitka") or importlib.util.find_spec("nuitka"))


def preflight(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    icon = root / "assets" / "branding" / "ForgePY.ico"
    bootstrap = root / "app" / "ForgePYBootstrap.py"
    assets = root / "assets"
    return {
        "schema": "forgepy.standalone-build-preflight.v2",
        "version": BUILD_VERSION,
        "root": str(root),
        "python": sys.executable,
        "nuitkaAvailable": _nuitka_available(),
        "icon": str(icon),
        "iconExists": icon.is_file(),
        "bootstrap": str(bootstrap),
        "bootstrapExists": bootstrap.is_file(),
        "assets": str(assets),
        "assetsExist": assets.is_dir(),
        "mode": "portable-onedir",
        "readyForWindowsBuild": sys.platform.startswith("win") and _nuitka_available() and icon.is_file() and bootstrap.is_file(),
        "selfUpdateReady": True,
        "selfUpdateNote": "Directory-transaction self-update uses the separate ForgePY maintenance lane and AppData/portable staging.",
    }



def dynamic_modules(root: Path) -> list[str]:
    """Include flat app modules that runtime compatibility hooks import dynamically."""
    app = root.expanduser().resolve() / "app"
    modules: list[str] = []
    if not app.is_dir():
        return modules
    for path in sorted(app.glob("*.py"), key=lambda p: p.name.casefold()):
        if path.name.startswith("_") or path.stem in {"ForgePYBootstrap"}:
            continue
        modules.append(path.stem)
    return modules


def command(root: Path, *, build_root: Path | None = None) -> list[str]:
    root = root.expanduser().resolve()
    info = preflight(root)
    build_root = (build_root or (root / "dist" / "nuitka")).expanduser().resolve()
    entry = root / "app" / "ForgePYBootstrap.py"
    icon = root / "assets" / "branding" / "ForgePY.ico"
    argv = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--enable-plugin=tk-inter",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={icon}",
        "--company-name=ForgePY",
        "--product-name=ForgePY",
        "--file-description=ForgePY Universal Project Operations",
        f"--file-version={NUMERIC_FILE_VERSION}",
        f"--product-version={NUMERIC_FILE_VERSION}",
        "--output-filename=ForgePY.exe",
        f"--output-dir={build_root}",
    ]
    assets = root / "assets"
    if info.get("assetsExist"):
        argv.append(f"--include-data-dir={assets}=assets")
    for module_name in dynamic_modules(root):
        argv.append(f"--include-module={module_name}")
    argv.append(str(entry))
    return argv


def expected_build_parent(root: Path) -> Path:
    return root.expanduser().resolve() / "dist" / "nuitka"


def portable_output(root: Path) -> Path:
    return root.expanduser().resolve() / "dist" / "ForgePY"
