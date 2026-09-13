#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from PCCProjectDiscovery import discover_project_contract_data

PROJECT_PCC_VERSION = "FORGEPY-PROJECT-PCC-1.0-F797"
_PATCH_SUFFIXES = {".patch", ".zip"}


def _resolve_shell(program: str) -> str:
    low = str(program or "").strip().casefold()
    if low in {"pwsh", "pwsh.exe"}:
        return shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
    if low in {"powershell", "powershell.exe"}:
        return shutil.which("powershell") or shutil.which("pwsh") or "powershell.exe"
    if low in {"python", "python.exe", "python3"}:
        return sys.executable
    if low in {"cmd", "cmd.exe"}:
        return os.environ.get("COMSPEC") or "cmd.exe"
    return shutil.which(program) or program


def _script_argv(path: Path, args: list[str] | None = None) -> list[str]:
    args = list(args or [])
    suffix = path.suffix.casefold()
    if suffix in {".cmd", ".bat"}:
        return [os.environ.get("COMSPEC") or "cmd.exe", "/d", "/s", "/c", str(path), *args]
    if suffix == ".ps1":
        return [_resolve_shell("pwsh"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path), *args]
    if suffix in {".py", ".pyw"}:
        return [sys.executable, str(path), *args]
    return [str(path), *args]


def profile(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    data = discover_project_contract_data(root)
    control = data.get("root_control_center") if isinstance(data.get("root_control_center"), dict) else {}
    commands = [x for x in (data.get("commands") or []) if isinstance(x, dict)]
    keys = {str(x.get("key") or "").casefold() for x in commands}
    launcher_raw = str(control.get("launcher") or "").strip()
    provider_raw = str(control.get("machine_provider") or control.get("python_provider") or control.get("discoveredPowerShell") or "").strip()
    launcher = (root / launcher_raw).resolve() if launcher_raw else None
    provider = (root / provider_raw).resolve() if provider_raw else None
    has_patch = bool(keys & {"patch.apply", "patch.apply-staged"})
    has_recovery = bool(keys & {"recovery.restore", "recovery.undo-last", "patch.undo", "patch.rollback"})
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    return {
        "schema": "forgepy.project-pcc.v1",
        "version": PROJECT_PCC_VERSION,
        "projectId": str(project.get("id") or root.name),
        "projectName": str(project.get("name") or root.name),
        "root": str(root),
        "launcher": str(launcher) if launcher and launcher.is_file() else "",
        "launcherDeclared": launcher_raw,
        "machineProvider": str(provider) if provider and provider.is_file() else "",
        "machineProviderDeclared": provider_raw,
        "machineProviderKind": provider.suffix.casefold().lstrip(".") if provider and provider.is_file() else "",
        "commands": sorted(keys),
        "hasInternalPcc": bool((launcher and launcher.is_file()) or commands or (provider and provider.is_file())),
        "hasPatchAuthority": has_patch,
        "hasRecoveryAuthority": has_recovery,
        "nativePatchReady": has_patch and has_recovery,
    }


def launcher_argv(root: Path) -> list[str]:
    info = profile(root)
    raw = str(info.get("launcher") or "")
    if not raw:
        raise RuntimeError("project does not declare an internal PCC launcher")
    return _script_argv(Path(raw))


def launch_control_center(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    argv = launcher_argv(root)
    flags = 0
    startupinfo = None
    if os.name == "nt":
        # Internal PCCs own their own UI/console experience. Do not force CREATE_NO_WINDOW.
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags &= ~int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
    proc = subprocess.Popen(argv, cwd=str(root), stdin=subprocess.DEVNULL, creationflags=flags, startupinfo=startupinfo)
    return {"launched": True, "pid": proc.pid, "argv": argv, "root": str(root)}


def _zip_has_patch_manifest(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = {n.replace("\\", "/").casefold() for n in zf.namelist()}
            return "patch_manifest.json" in names
    except Exception:
        return False


def root_patch_transports(root: Path, *, include_inbox: bool = True) -> list[Path]:
    """Bounded project-owned root/inbox patch discovery.

    This deliberately does not recurse. Existing internal PCCs commonly own exactly these
    two locations, so Forge can preserve and delegate the same bytes rather than moving them
    out from underneath the project provider.
    """
    root = root.expanduser().resolve()
    folders = [root]
    if include_inbox:
        folders.append(root / "updates" / "inbox")
    rows: list[Path] = []
    seen: set[str] = set()
    for folder in folders:
        if not folder.is_dir():
            continue
        try:
            candidates = list(folder.iterdir())[:512]
        except OSError:
            continue
        for path in candidates:
            if not path.is_file() or path.suffix.casefold() not in _PATCH_SUFFIXES:
                continue
            # .patch is accepted directly; ZIP must carry a top-level patch manifest.
            if path.suffix.casefold() == ".zip" and not _zip_has_patch_manifest(path):
                continue
            key = os.path.normcase(str(path.resolve()))
            if key not in seen:
                seen.add(key)
                rows.append(path.resolve())
    return sorted(rows, key=lambda p: p.name.casefold())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stage_exact_transport(root: Path, source: Path) -> dict[str, Any]:
    """Make one exact transport available to a project-owned PCC without rewriting it.

    If the file is already in the project root or updates/inbox, it is left exactly where the
    operator placed it. Otherwise it is copied hash-for-hash to updates/inbox. This is a bridge,
    not a conversion: the project's native patch authority still validates and applies it.
    """
    root = root.expanduser().resolve()
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    info = profile(root)
    if not info.get("nativePatchReady"):
        raise RuntimeError("project does not expose both native patch and recovery authority")
    digest = sha256_file(source)
    for existing in root_patch_transports(root, include_inbox=True):
        try:
            if existing == source or sha256_file(existing) == digest:
                return {"source": str(source), "projectPath": str(existing), "sha256": digest, "copied": False}
        except OSError:
            pass
    inbox = root / "updates" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / source.name
    if dest.exists() and sha256_file(dest) != digest:
        dest = inbox / f"{source.stem}-{digest[:10]}{source.suffix}"
    if not dest.exists():
        temp = dest.with_suffix(dest.suffix + ".forge-copying")
        shutil.copy2(source, temp)
        if sha256_file(temp) != digest:
            temp.unlink(missing_ok=True)
            raise RuntimeError("project-native transport bridge hash mismatch")
        os.replace(temp, dest)
    return {"source": str(source), "projectPath": str(dest), "sha256": digest, "copied": source != dest}


__all__ = [
    "PROJECT_PCC_VERSION", "profile", "launcher_argv", "launch_control_center",
    "root_patch_transports", "stage_exact_transport", "sha256_file",
]
