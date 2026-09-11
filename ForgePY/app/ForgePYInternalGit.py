#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Sequence

from ForgePYPaths import data_root
from ForgePYSettings import load_settings

INTERNAL_GIT_VERSION = "FORGEPY-INTERNAL-GIT-0.1"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-.") or "project"


def internal_git_root() -> Path:
    cfg = load_settings().get("sourceControl") or {}
    raw = str(cfg.get("internalGitRoot") or "").strip()
    return Path(raw).expanduser() if raw else data_root() / "InternalGit"


def repository_path(project_id: str) -> Path:
    return internal_git_root() / f"{_safe_id(project_id)}.git"


def remote_name() -> str:
    cfg = load_settings().get("sourceControl") or {}
    return str(cfg.get("defaultInternalGitRemote") or "forgepy-internal").strip() or "forgepy-internal"


def enabled() -> bool:
    return bool((load_settings().get("sourceControl") or {}).get("internalGitEnabled", True))


def _git_exe() -> str:
    configured = str((load_settings().get("sourceControl") or {}).get("gitBinary") or "").strip()
    if configured and Path(configured).expanduser().is_file():
        return str(Path(configured).expanduser().resolve())
    return shutil.which("git") or "git"


def _run(*args: str, cwd: Path | None = None, timeout: float = 180.0) -> subprocess.CompletedProcess[str]:
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
        startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
    return subprocess.run(
        [_git_exe(), *args],
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=creationflags,
        startupinfo=startupinfo,
    )


def status(project_root: Path, project_id: str) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    repo = repository_path(project_id)
    name = remote_name()
    result: dict[str, Any] = {
        "schema": "forgepy.internal_git.status.v1",
        "version": INTERNAL_GIT_VERSION,
        "enabled": enabled(),
        "gitReady": bool(shutil.which("git") or Path(_git_exe()).exists()),
        "workingTree": str(root),
        "projectId": project_id,
        "repository": str(repo),
        "repositoryReady": repo.is_dir() and (repo / "HEAD").is_file(),
        "remoteName": name,
        "remoteConfigured": False,
        "head": "",
        "branch": "",
        "error": "",
    }
    if not (root / ".git").exists() or not result["gitReady"]:
        return result
    cp = _run("-C", str(root), "remote", "get-url", name, timeout=15)
    if cp.returncode == 0:
        try:
            result["remoteConfigured"] = Path(cp.stdout.strip()).expanduser().resolve() == repo.expanduser().resolve()
        except Exception:
            result["remoteConfigured"] = cp.stdout.strip() == str(repo)
    head = _run("-C", str(root), "rev-parse", "HEAD", timeout=15)
    if head.returncode == 0:
        result["head"] = head.stdout.strip()
    branch = _run("-C", str(root), "branch", "--show-current", timeout=15)
    if branch.returncode == 0:
        result["branch"] = branch.stdout.strip()
    return result


def ensure(project_root: Path, project_id: str) -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    repo = repository_path(project_id)
    name = remote_name()
    out: list[str] = []
    if not enabled():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] ForgePY Internal Git is disabled in settings.\n")
    if not (root / ".git").exists():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] Working tree is not initialized as Git. Use Initialize / Adopt Git first.\n")
    repo.parent.mkdir(parents=True, exist_ok=True)
    if not (repo / "HEAD").is_file():
        cp = _run("init", "--bare", str(repo), timeout=60)
        if cp.stdout.strip():
            out.append(cp.stdout.rstrip())
        if cp.returncode != 0:
            return subprocess.CompletedProcess([], cp.returncode, stdout="\n".join(out) + "\n")
        out.append(f"[PASS] Created ForgePY Internal Git repository: {repo}")
    else:
        out.append(f"[PASS] ForgePY Internal Git repository ready: {repo}")
    cur = _run("-C", str(root), "remote", "get-url", name, timeout=15)
    if cur.returncode == 0:
        try:
            same = Path(cur.stdout.strip()).expanduser().resolve() == repo.resolve()
        except Exception:
            same = cur.stdout.strip() == str(repo)
        if not same:
            out.append(f"[FAIL] Existing remote {name} points elsewhere: {cur.stdout.strip()}")
            return subprocess.CompletedProcess([], 2, stdout="\n".join(out) + "\n")
        out.append(f"[PASS] Internal remote already bound: {name}")
    else:
        cp = _run("-C", str(root), "remote", "add", name, str(repo), timeout=30)
        if cp.stdout.strip():
            out.append(cp.stdout.rstrip())
        if cp.returncode != 0:
            return subprocess.CompletedProcess([], cp.returncode, stdout="\n".join(out) + "\n")
        out.append(f"[PASS] Bound working tree remote {name} -> {repo}")
    return subprocess.CompletedProcess([], 0, stdout="\n".join(out) + "\n")


def push_snapshot(project_root: Path, project_id: str) -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    prep = ensure(root, project_id)
    if prep.returncode != 0:
        return prep
    head = _run("-C", str(root), "rev-parse", "--verify", "HEAD", timeout=15)
    if head.returncode != 0:
        return subprocess.CompletedProcess([], 2, stdout=prep.stdout + "[FAIL] No commit exists to snapshot.\n")
    branch = _run("-C", str(root), "branch", "--show-current", timeout=15).stdout.strip() or "main"
    cp = _run("-C", str(root), "push", remote_name(), f"HEAD:refs/heads/{branch}", timeout=300)
    prefix = prep.stdout + f"[INFO] Snapshotting {head.stdout.strip()[:12]} to ForgePY Internal Git / {branch}.\n"
    if cp.returncode == 0:
        prefix += f"[PASS] Internal Git snapshot current: {repository_path(project_id)}\n"
    return subprocess.CompletedProcess([], cp.returncode, stdout=prefix + cp.stdout)


def history(project_id: str) -> subprocess.CompletedProcess[str]:
    repo = repository_path(project_id)
    if not (repo / "HEAD").is_file():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] Internal Git repository does not exist yet.\n")
    return _run("--git-dir", str(repo), "log", "--oneline", "--decorate", "--graph", "--all", "-40")


def command(project_root: Path, project_id: str, action: str) -> subprocess.CompletedProcess[str]:
    if action == "ensure":
        return ensure(project_root, project_id)
    if action == "push":
        return push_snapshot(project_root, project_id)
    if action == "history":
        return history(project_id)
    if action == "status":
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(status(project_root, project_id), indent=2, sort_keys=True) + "\n")
    raise ValueError(action)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ForgePY Internal Git local authority")
    ap.add_argument("action", choices=("status", "ensure", "push", "history"))
    ap.add_argument("--root", required=True)
    ap.add_argument("--project-id", required=True)
    ns = ap.parse_args(argv)
    cp = command(Path(ns.root), ns.project_id, ns.action)
    print(cp.stdout, end="")
    return int(cp.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
