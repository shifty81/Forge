#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from VaultSettings import load_settings

IDE_VERSION = "VAULT-IDE-0.4.1"
SOURCE_WEB = Path(__file__).resolve().parents[1] / "web" / "ide"
TEXT_EXTS = {".py", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".java", ".js", ".ts", ".json", ".toml", ".ron", ".md", ".txt", ".ps1", ".cmd", ".bat", ".sh", ".html", ".css", ".xml", ".yaml", ".yml", ".ini", ".cfg"}
SKIP = {".git", "target", "node_modules", ".venv", "venv", "build", "dist", "__pycache__"}


def monaco_root() -> Path:
    value = str((load_settings().get("ide") or {}).get("monacoRoot") or "").strip()
    return Path(value).expanduser() if value else Path.home() / ".vault" / "Monaco"


def runtime_ready() -> bool:
    root = monaco_root()
    # 0.56 still ships the compatibility loader. Vault keeps the runtime local and
    # will move to an ESM bundle without changing the Python IDE contract.
    return (root / "index.html").is_file() and (root / "node_modules" / "monaco-editor" / "min" / "vs" / "loader.js").is_file()


def host_ready() -> bool:
    try:
        import webview  # type: ignore
        return bool(webview)
    except Exception:
        return False


def prepare_runtime() -> Path:
    root = monaco_root()
    root.mkdir(parents=True, exist_ok=True)
    if SOURCE_WEB.is_dir():
        for p in SOURCE_WEB.iterdir():
            if p.is_file():
                shutil.copy2(p, root / p.name)
    return root


def install_host() -> subprocess.CompletedProcess[str]:
    """Install ForgePY's separate Monaco-window host.

    pywebview is BSD-3-Clause and uses WebView2 on modern Windows systems. Keeping
    it in a separate process prevents a WebView crash from taking down the Tk
    recovery/control surface.
    """
    version = str((load_settings().get("ide") or {}).get("pywebviewVersion") or "6.2.1")
    return subprocess.run(
        [os.fspath(Path(sys.executable)), "-m", "pip", "install", f"pywebview=={version}"],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def install_monaco() -> subprocess.CompletedProcess[str]:
    root = prepare_runtime()
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        return subprocess.CompletedProcess([], 127, stdout="npm was not found; native Vault editor remains available.\n")
    version = str((load_settings().get("ide") or {}).get("monacoVersion") or "0.56.0")
    return subprocess.run(
        [npm, "install", "--no-audit", "--no-fund", f"monaco-editor@{version}"],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def confined(root: Path, value: str | Path) -> Path:
    root = root.expanduser().resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionError("IDE access is confined to the active project root") from exc
    return candidate


def read_file(root: Path, value: str | Path) -> dict[str, Any]:
    p = confined(root, value)
    if not p.is_file():
        raise FileNotFoundError(p)
    if p.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("IDE text file exceeds 8 MiB safety limit")
    data = p.read_text(encoding="utf-8", errors="replace")
    return {"path": str(p), "relative": p.relative_to(root.resolve()).as_posix(), "text": data}


def write_file(root: Path, value: str | Path, text: str) -> dict[str, Any]:
    p = confined(root, value)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix + ".vault-saving")
    temp.write_text(str(text), encoding="utf-8", newline="\n")
    os.replace(temp, p)
    return {"path": str(p), "relative": p.relative_to(root.resolve()).as_posix(), "bytes": p.stat().st_size}


def list_files(root: Path, *, max_files: int = 12000) -> list[str]:
    root = root.expanduser().resolve()
    out: list[str] = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.casefold() not in SKIP]
        b = Path(base)
        for name in files:
            p = b / name
            if p.suffix.casefold() not in TEXT_EXTS:
                continue
            out.append(p.relative_to(root).as_posix())
            if len(out) >= max_files:
                return sorted(out, key=str.casefold)
    return sorted(out, key=str.casefold)


def launch_monaco(root: Path, *, initial_file: str = "") -> subprocess.Popen[str]:
    """Launch Monaco as a separate Vault-owned editor process/window."""
    root = root.expanduser().resolve()
    if not runtime_ready():
        raise RuntimeError("Monaco runtime is not installed")
    if not host_ready():
        raise RuntimeError("pywebview host is not installed")
    window_script = Path(__file__).resolve().parent / "VaultIdeWindow.py"
    argv = [sys.executable, str(window_script), "--root", str(root)]
    if initial_file:
        argv += ["--file", initial_file]
    kwargs: dict[str, Any] = {
        "cwd": str(root),
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if os.name == "nt":
        kwargs["creationflags"] = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.Popen(argv, **kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ForgePY IDE support")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("install-monaco")
    sp.add_parser("install-host")
    sp.add_parser("status")
    launch = sp.add_parser("launch")
    launch.add_argument("--root", required=True)
    launch.add_argument("--file", default="")
    ns = p.parse_args(argv)
    if ns.cmd == "install-monaco":
        cp = install_monaco(); print(cp.stdout or "", end=""); return int(cp.returncode)
    if ns.cmd == "install-host":
        cp = install_host(); print(cp.stdout or "", end=""); return int(cp.returncode)
    if ns.cmd == "launch":
        launch_monaco(Path(ns.root), initial_file=str(ns.file or "")); return 0
    print(json.dumps({
        "version": IDE_VERSION,
        "monacoRoot": str(monaco_root()),
        "runtimeReady": runtime_ready(),
        "webViewHost": "pywebview",
        "webViewHostReady": host_ready(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
