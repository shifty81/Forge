#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from VaultIde import host_ready, runtime_ready

COMPONENTS_VERSION = "VAULT-COMPONENTS-0.4"


@dataclass(frozen=True)
class Component:
    key: str
    name: str
    purpose: str
    license: str
    kind: str
    detected: bool
    location: str = ""
    recommended: bool = True


def _module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _binary(*names: str) -> str:
    for name in names:
        value = shutil.which(name)
        if value:
            return value
    return ""


def inventory() -> dict[str, Any]:
    rg = _binary("rg", "rg.exe")
    rows = [
        Component("monaco", "Monaco Editor", "ForgePY IDE editing surface", "MIT", "local-web", runtime_ready(), recommended=True),
        Component("pywebview", "pywebview", "Separate Monaco desktop window / WebView2 host", "BSD-3-Clause", "python", host_ready(), recommended=True),
        Component("watchfiles", "watchfiles", "Native high-performance filesystem watching", "MIT", "python", _module("watchfiles"), recommended=True),
        Component("tree-sitter", "Tree-sitter", "Incremental source parsing/indexing", "MIT", "python", _module("tree_sitter"), recommended=True),
        Component("ripgrep", "ripgrep", "Fast project/source search respecting ignore files", "MIT OR Unlicense", "binary", bool(rg), rg, True),
        Component("psutil", "psutil", "Process/service/resource health telemetry", "BSD-3-Clause", "python", _module("psutil"), recommended=True),
    ]
    return {"schema": "vault.components.v1", "version": COMPONENTS_VERSION, "components": [asdict(x) for x in rows]}


def install_python(package: str) -> subprocess.CompletedProcess[str]:
    allow = {
        "pywebview": "pywebview==6.2.1",
        "watchfiles": "watchfiles",
        "tree-sitter": "tree-sitter",
        "psutil": "psutil",
    }
    spec = allow.get(package)
    if not spec:
        return subprocess.CompletedProcess([], 2, stdout=f"Unsupported Vault component: {package}\n")
    return subprocess.run([sys.executable, "-m", "pip", "install", spec], text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def write_inventory(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


__all__ = ["COMPONENTS_VERSION", "inventory", "install_python", "write_inventory"]
