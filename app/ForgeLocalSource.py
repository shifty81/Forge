#!/usr/bin/env python3
"""Friendly Local Source facade over ForgePY's existing ForgeGit authority.

ForgeGit remains the on-disk compatibility implementation in F60R415.  New UI code
speaks in terms of Local Source and routes through this facade so the internal rename
can happen incrementally without moving or rewriting existing history.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ForgeGit import (
    _run as _git_run,
    branches as _branches,
    ensure as _ensure,
    remote_name as _local_remote_name,
    restore_branch as _restore_branch,
)

LOCAL_SOURCE_VERSION = "FORGEPY-LOCAL-SOURCE-1.0"


def branch_names(project_root: Path) -> list[str]:
    rows = list(_branches(project_root) or [])
    out: list[str] = []
    for row in rows:
        if bool(row.get("remote")):
            continue
        name = str(row.get("name") or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def _verify_branch(root: Path, branch: str) -> subprocess.CompletedProcess[str] | None:
    cp = _git_run("-C", str(root), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", timeout=20)
    if cp.returncode == 0:
        return None
    return subprocess.CompletedProcess([], 2, stdout=f"[FAIL] Local branch does not exist: {branch}\n")


def backup_branch(project_root: Path, project_id: str, branch: str) -> subprocess.CompletedProcess[str]:
    """Back up exactly one chosen local branch to Local Source without switching branches."""
    root = project_root.expanduser().resolve()
    branch = str(branch or "").strip()
    prep = _ensure(root, project_id)
    if prep.returncode != 0:
        return prep
    missing = _verify_branch(root, branch)
    if missing is not None:
        return missing
    remote = _local_remote_name()
    cp = _git_run("-C", str(root), "push", remote, f"refs/heads/{branch}:refs/heads/{branch}", timeout=300)
    prefix = prep.stdout + f"[INFO] Backing up branch {branch} to Local Source.\n"
    if cp.returncode == 0:
        prefix += f"[PASS] Local Source branch backup current: {branch}\n"
    return subprocess.CompletedProcess([], cp.returncode, stdout=prefix + cp.stdout)


def restore_branch(project_root: Path, project_id: str, branch: str, recovery_branch: str) -> subprocess.CompletedProcess[str]:
    """Recover one Local Source branch into a new working branch; never force-reset current files."""
    return _restore_branch(project_root, project_id, branch, recovery_branch)


def backup_github_branch(project_root: Path, branch: str, remote: str = "origin") -> subprocess.CompletedProcess[str]:
    """Push one selected branch to GitHub without force."""
    root = project_root.expanduser().resolve()
    branch = str(branch or "").strip()
    remote = str(remote or "origin").strip() or "origin"
    missing = _verify_branch(root, branch)
    if missing is not None:
        return missing
    remote_check = _git_run("-C", str(root), "remote", "get-url", remote, timeout=20)
    if remote_check.returncode != 0:
        return subprocess.CompletedProcess([], 2, stdout=f"[FAIL] GitHub remote is not configured: {remote}\n")
    cp = _git_run("-C", str(root), "push", remote, f"refs/heads/{branch}:refs/heads/{branch}", timeout=300)
    prefix = f"[INFO] Backing up branch {branch} to GitHub remote {remote}.\n"
    if cp.returncode == 0:
        prefix += f"[PASS] GitHub branch backup current: {branch}\n"
    else:
        prefix += "[WARN] GitHub rejected the push. ForgePY did not force-push.\n"
    return subprocess.CompletedProcess([], cp.returncode, stdout=prefix + cp.stdout)


def restore_github_branch(project_root: Path, branch: str, remote: str = "origin") -> subprocess.CompletedProcess[str]:
    """Safely fast-forward one selected branch from GitHub; divergent history fails closed."""
    root = project_root.expanduser().resolve()
    branch = str(branch or "").strip()
    remote = str(remote or "origin").strip() or "origin"
    dirty = _git_run("-C", str(root), "status", "--porcelain", timeout=20)
    if dirty.returncode != 0:
        return dirty
    if dirty.stdout.strip():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] Working tree is dirty. Back up or commit before restore.\n")
    fetch = _git_run("-C", str(root), "fetch", remote, branch, timeout=300)
    if fetch.returncode != 0:
        return fetch
    current = _git_run("-C", str(root), "branch", "--show-current", timeout=20).stdout.strip()
    exists = _verify_branch(root, branch) is None
    out = fetch.stdout
    if current != branch:
        if exists:
            sw = _git_run("-C", str(root), "switch", branch, timeout=60)
        else:
            sw = _git_run("-C", str(root), "switch", "-c", branch, "--track", f"{remote}/{branch}", timeout=60)
        out += sw.stdout
        if sw.returncode != 0:
            return subprocess.CompletedProcess([], sw.returncode, stdout=out)
    ff = _git_run("-C", str(root), "merge", "--ff-only", f"{remote}/{branch}", timeout=300)
    out += ff.stdout
    prefix = f"[INFO] Restoring branch {branch} from GitHub remote {remote} with fast-forward only.\n"
    if ff.returncode == 0:
        prefix += f"[PASS] GitHub restore current: {branch}\n"
    else:
        prefix += "[WARN] Branch diverged. ForgePY did not reset or overwrite local history.\n"
    return subprocess.CompletedProcess([], ff.returncode, stdout=prefix + out)


def summary(project_root: Path, project_id: str) -> dict[str, Any]:
    from ForgeGit import status
    data = dict(status(project_root, project_id) or {})
    data["displayAuthority"] = "Local Source"
    data["version"] = LOCAL_SOURCE_VERSION
    return data
