#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ForgePYPaths import data_root
from ForgePYSettings import load_settings

FORGEGIT_VERSION = "FORGEGIT-0.2"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-.") or "project"


def _settings() -> dict[str, Any]:
    return dict(load_settings().get("sourceControl") or {})


def forgegit_root() -> Path:
    cfg = _settings()
    raw = str(cfg.get("forgeGitRoot") or "").strip()
    if raw:
        return Path(raw).expanduser()
    # Preserve the user's existing local history after the Internal Git -> ForgeGit rename.
    legacy = str(cfg.get("internalGitRoot") or "").strip()
    if legacy and Path(legacy).expanduser().exists():
        return Path(legacy).expanduser()
    return data_root() / "ForgeGit"


def legacy_root() -> Path:
    cfg = _settings()
    raw = str(cfg.get("internalGitRoot") or "").strip()
    return Path(raw).expanduser() if raw else data_root() / "InternalGit"


def repository_path(project_id: str) -> Path:
    preferred = forgegit_root() / f"{_safe_id(project_id)}.git"
    if preferred.exists():
        return preferred
    legacy = legacy_root() / f"{_safe_id(project_id)}.git"
    if legacy.exists():
        return legacy
    return preferred


def remote_name() -> str:
    cfg = _settings()
    return str(cfg.get("defaultForgeGitRemote") or cfg.get("defaultInternalGitRemote") or "forgegit").strip() or "forgegit"


def legacy_remote_names() -> tuple[str, ...]:
    cfg = _settings()
    legacy = str(cfg.get("defaultInternalGitRemote") or "forgepy-internal").strip() or "forgepy-internal"
    return tuple(dict.fromkeys((remote_name(), legacy, "forgepy-internal")))


def enabled() -> bool:
    cfg = _settings()
    if "forgeGitEnabled" in cfg:
        return bool(cfg.get("forgeGitEnabled"))
    return bool(cfg.get("internalGitEnabled", True))


def _git_exe() -> str:
    configured = str(_settings().get("gitBinary") or "").strip()
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
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(
        [_git_exe(), *args], cwd=str(cwd) if cwd else None,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
        creationflags=creationflags, startupinfo=startupinfo, env=env,
    )


def _current_branch(root: Path) -> str:
    cp = _run("-C", str(root), "branch", "--show-current", timeout=15)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def _head(root: Path) -> str:
    cp = _run("-C", str(root), "rev-parse", "HEAD", timeout=15)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def _remote_url(root: Path, name: str) -> str:
    cp = _run("-C", str(root), "remote", "get-url", name, timeout=15)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def status(project_root: Path, project_id: str) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    repo = repository_path(project_id)
    configured_remote = ""
    configured_name = ""
    if (root / ".git").exists():
        for name in legacy_remote_names():
            url = _remote_url(root, name)
            if url:
                configured_name, configured_remote = name, url
                break
    expected = str(repo.resolve()) if repo.exists() else str(repo)
    same = False
    if configured_remote:
        try:
            same = str(Path(configured_remote).expanduser().resolve()) == expected
        except Exception:
            same = configured_remote == str(repo)
    return {
        "schema": "forgegit.status.v1",
        "version": FORGEGIT_VERSION,
        "enabled": enabled(),
        "gitReady": bool(shutil.which("git") or Path(_git_exe()).exists()),
        "workingTree": str(root),
        "projectId": project_id,
        "repository": str(repo),
        "repositoryReady": repo.is_dir() and (repo / "HEAD").is_file(),
        "remoteName": configured_name or remote_name(),
        "remoteConfigured": same,
        "legacyRemote": bool(configured_name and configured_name != remote_name()),
        "head": _head(root) if (root / ".git").exists() else "",
        "branch": _current_branch(root) if (root / ".git").exists() else "",
        "error": "",
    }


def ensure(project_root: Path, project_id: str) -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    repo = repository_path(project_id)
    name = remote_name()
    out: list[str] = []
    if not enabled():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] ForgeGit is disabled in settings.\n")
    if not (root / ".git").exists():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] Working tree is not initialized as Git. Use Initialize / Adopt Git first.\n")
    repo.parent.mkdir(parents=True, exist_ok=True)
    if not (repo / "HEAD").is_file():
        cp = _run("init", "--bare", str(repo), timeout=60)
        if cp.stdout.strip(): out.append(cp.stdout.rstrip())
        if cp.returncode != 0:
            return subprocess.CompletedProcess([], cp.returncode, stdout="\n".join(out) + "\n")
        out.append(f"[PASS] Created ForgeGit repository: {repo}")
    else:
        out.append(f"[PASS] ForgeGit repository ready: {repo}")

    # Adopt an existing legacy remote if it already points to this repository. Otherwise
    # create the canonical ForgeGit remote without deleting the compatibility remote.
    for candidate in legacy_remote_names():
        url = _remote_url(root, candidate)
        if not url:
            continue
        try:
            same = Path(url).expanduser().resolve() == repo.resolve()
        except Exception:
            same = url == str(repo)
        if same:
            if candidate == name:
                out.append(f"[PASS] ForgeGit remote already bound: {name}")
                return subprocess.CompletedProcess([], 0, stdout="\n".join(out) + "\n")
            out.append(f"[PASS] Adopted legacy ForgeGit remote {candidate}; history preserved.")
            add = _run("-C", str(root), "remote", "add", name, str(repo), timeout=30)
            if add.returncode == 0:
                out.append(f"[PASS] Added canonical ForgeGit remote {name} -> {repo}")
            elif "already exists" not in add.stdout.casefold():
                out.append(add.stdout.rstrip())
                return subprocess.CompletedProcess([], add.returncode, stdout="\n".join(out) + "\n")
            return subprocess.CompletedProcess([], 0, stdout="\n".join(out) + "\n")

    cur = _remote_url(root, name)
    if cur:
        out.append(f"[FAIL] Existing remote {name} points elsewhere: {cur}")
        return subprocess.CompletedProcess([], 2, stdout="\n".join(out) + "\n")
    cp = _run("-C", str(root), "remote", "add", name, str(repo), timeout=30)
    if cp.stdout.strip(): out.append(cp.stdout.rstrip())
    if cp.returncode != 0:
        return subprocess.CompletedProcess([], cp.returncode, stdout="\n".join(out) + "\n")
    out.append(f"[PASS] Bound working tree remote {name} -> {repo}")
    return subprocess.CompletedProcess([], 0, stdout="\n".join(out) + "\n")


def push_snapshot(project_root: Path, project_id: str, *, ref_name: str = "") -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    prep = ensure(root, project_id)
    if prep.returncode != 0: return prep
    head = _head(root)
    if not head:
        return subprocess.CompletedProcess([], 2, stdout=prep.stdout + "[FAIL] No commit exists to snapshot.\n")
    branch = ref_name.strip() or _current_branch(root) or "main"
    cp = _run("-C", str(root), "push", remote_name(), f"HEAD:refs/heads/{branch}", timeout=300)
    prefix = prep.stdout + f"[INFO] Snapshotting {head[:12]} to ForgeGit / {branch}.\n"
    if cp.returncode == 0:
        prefix += f"[PASS] ForgeGit snapshot current: {repository_path(project_id)}\n"
    return subprocess.CompletedProcess([], cp.returncode, stdout=prefix + cp.stdout)


def history(project_id: str, limit: int = 80) -> subprocess.CompletedProcess[str]:
    repo = repository_path(project_id)
    if not (repo / "HEAD").is_file():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] ForgeGit repository does not exist yet.\n")
    return _run("--git-dir", str(repo), "log", "--oneline", "--decorate", "--graph", "--all", f"-{max(1, limit)}")


def branches(project_root: Path) -> list[dict[str, Any]]:
    root = project_root.expanduser().resolve()
    if not (root / ".git").exists(): return []
    fmt = "%(refname:short)|%(objectname:short)|%(upstream:short)|%(HEAD)|%(committerdate:iso8601-strict)"
    cp = _run("-C", str(root), "for-each-ref", "--sort=-committerdate", f"--format={fmt}", "refs/heads", "refs/remotes", timeout=30)
    rows: list[dict[str, Any]] = []
    if cp.returncode != 0: return rows
    for line in cp.stdout.splitlines():
        parts = line.split("|", 4)
        if len(parts) != 5: continue
        name, head, upstream, current, modified = parts
        rows.append({
            "name": name, "head": head, "upstream": upstream,
            "current": current.strip() == "*", "modified": modified,
            "remote": name.startswith("remotes/") or "/" in name and name.split("/",1)[0] in {"origin", remote_name(), "forgepy-internal"},
        })
    return rows


def _check_branch_name(root: Path, name: str) -> tuple[bool, str]:
    value = str(name or "").strip()
    if not value: return False, "branch name is empty"
    cp = _run("-C", str(root), "check-ref-format", "--branch", value, timeout=15)
    return (cp.returncode == 0, cp.stdout.strip())


def create_branch(project_root: Path, name: str, start: str = "HEAD", *, switch: bool = True) -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    ok, reason = _check_branch_name(root, name)
    if not ok: return subprocess.CompletedProcess([], 2, stdout=f"[FAIL] Invalid branch name {name!r}: {reason}\n")
    args = ["switch", "-c", name, start] if switch else ["branch", name, start]
    cp = _run("-C", str(root), *args, timeout=60)
    if cp.returncode == 0:
        prefix = f"[PASS] Created branch {name} from {start}" + (" and switched to it.\n" if switch else ".\n")
        return subprocess.CompletedProcess([], 0, stdout=prefix + cp.stdout)
    return cp


def switch_branch(project_root: Path, name: str) -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    cp = _run("-C", str(root), "switch", name, timeout=60)
    if cp.returncode == 0:
        return subprocess.CompletedProcess([], 0, stdout=f"[PASS] Switched to branch {name}.\n" + cp.stdout)
    return cp


def rename_branch(project_root: Path, old: str, new: str) -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    ok, reason = _check_branch_name(root, new)
    if not ok: return subprocess.CompletedProcess([], 2, stdout=f"[FAIL] Invalid branch name {new!r}: {reason}\n")
    cp = _run("-C", str(root), "branch", "-m", old, new, timeout=60)
    if cp.returncode == 0:
        return subprocess.CompletedProcess([], 0, stdout=f"[PASS] Renamed branch {old} -> {new}.\n" + cp.stdout)
    return cp


def delete_branch(project_root: Path, name: str, *, force: bool = False) -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    if name == _current_branch(root):
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] Cannot delete the current branch. Switch branches first.\n")
    return _run("-C", str(root), "branch", "-D" if force else "-d", name, timeout=60)


def merge_branch(project_root: Path, name: str) -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    return _run("-C", str(root), "merge", "--no-edit", name, timeout=300)


def create_recovery_branch(project_root: Path, label: str = "") -> subprocess.CompletedProcess[str]:
    root = project_root.expanduser().resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    clean = _safe_id(label).casefold() if label.strip() else "snapshot"
    name = f"forgegit/recovery/{stamp}-{clean}"
    return create_branch(root, name, "HEAD", switch=False)



def verify(project_id: str) -> subprocess.CompletedProcess[str]:
    """Run a non-destructive object/ref integrity check on the local ForgeGit authority."""
    repo = repository_path(project_id)
    if not (repo / "HEAD").is_file():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] ForgeGit repository does not exist yet.\n")
    cp = _run("--git-dir", str(repo), "fsck", "--full", timeout=300)
    prefix = "[PASS] ForgeGit repository integrity verified.\n" if cp.returncode == 0 else "[FAIL] ForgeGit integrity check reported errors.\n"
    return subprocess.CompletedProcess([], cp.returncode, stdout=prefix + cp.stdout)


def export_bundle(project_id: str, destination: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Create a portable Git bundle containing every ForgeGit ref."""
    repo = repository_path(project_id)
    if not (repo / "HEAD").is_file():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] ForgeGit repository does not exist yet.\n")
    if destination is None:
        from ForgePYPaths import ensure_artifact_project_tree
        folder = ensure_artifact_project_tree(project_id)["reports"] / "source-control" / "forgegit-bundles"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        destination = folder / f"{_safe_id(project_id)}-{stamp}.bundle"
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    cp = _run("--git-dir", str(repo), "bundle", "create", str(destination), "--all", timeout=300)
    if cp.returncode == 0:
        verify_cp = _run("--git-dir", str(repo), "bundle", "verify", str(destination), timeout=120)
        if verify_cp.returncode != 0:
            destination.unlink(missing_ok=True)
            return subprocess.CompletedProcess([], verify_cp.returncode, stdout="[FAIL] ForgeGit bundle verification failed.\n" + verify_cp.stdout)
        return subprocess.CompletedProcess([], 0, stdout=f"[PASS] ForgeGit recovery bundle created and verified: {destination}\n")
    return cp


def optimize(project_id: str) -> subprocess.CompletedProcess[str]:
    """Explicit maintenance: repack/prune the bare authority without touching the working tree."""
    repo = repository_path(project_id)
    if not (repo / "HEAD").is_file():
        return subprocess.CompletedProcess([], 2, stdout="[FAIL] ForgeGit repository does not exist yet.\n")
    cp = _run("--git-dir", str(repo), "gc", timeout=600)
    prefix = "[PASS] ForgeGit repository maintenance complete.\n" if cp.returncode == 0 else "[FAIL] ForgeGit repository maintenance failed.\n"
    return subprocess.CompletedProcess([], cp.returncode, stdout=prefix + cp.stdout)


def restore_branch(project_root: Path, project_id: str, branch: str, local_name: str = "") -> subprocess.CompletedProcess[str]:
    """Recover one ForgeGit branch into the working repository without rewriting current files."""
    root = project_root.expanduser().resolve()
    prep = ensure(root, project_id)
    if prep.returncode != 0:
        return prep
    remote = remote_name()
    fetch = _run("-C", str(root), "fetch", remote, "+refs/heads/*:refs/remotes/%s/*" % remote, timeout=300)
    if fetch.returncode != 0:
        return fetch
    source_ref = f"{remote}/{branch}"
    target = (local_name or f"forgegit-restore/{_safe_id(branch)}").strip()
    ok, reason = _check_branch_name(root, target)
    if not ok:
        return subprocess.CompletedProcess([], 2, stdout=f"[FAIL] Invalid restore branch name {target!r}: {reason}\n")
    exists = _run("-C", str(root), "show-ref", "--verify", "--quiet", f"refs/heads/{target}", timeout=15)
    if exists.returncode == 0:
        return subprocess.CompletedProcess([], 2, stdout=f"[FAIL] Local branch {target} already exists. Choose another restore name.\n")
    cp = _run("-C", str(root), "branch", target, source_ref, timeout=60)
    if cp.returncode == 0:
        return subprocess.CompletedProcess([], 0, stdout=f"[PASS] Recovered ForgeGit {branch} as local branch {target}.\n" + cp.stdout)
    return cp

def command(project_root: Path, project_id: str, action: str, *extra: str) -> subprocess.CompletedProcess[str]:
    if action == "ensure": return ensure(project_root, project_id)
    if action == "push": return push_snapshot(project_root, project_id)
    if action == "history": return history(project_id)
    if action == "status": return subprocess.CompletedProcess([], 0, stdout=json.dumps(status(project_root, project_id), indent=2, sort_keys=True) + "\n")
    if action == "branches": return subprocess.CompletedProcess([], 0, stdout=json.dumps(branches(project_root), indent=2) + "\n")
    if action == "create-branch": return create_branch(project_root, extra[0], extra[1] if len(extra) > 1 else "HEAD", switch=True)
    if action == "switch-branch": return switch_branch(project_root, extra[0])
    if action == "rename-branch": return rename_branch(project_root, extra[0], extra[1])
    if action == "delete-branch": return delete_branch(project_root, extra[0], force="--force" in extra[1:])
    if action == "merge-branch": return merge_branch(project_root, extra[0])
    if action == "recovery-branch": return create_recovery_branch(project_root, extra[0] if extra else "")
    if action == "verify": return verify(project_id)
    if action == "export-bundle":
        destination = Path(extra[0]).expanduser() if extra else None
        return export_bundle(project_id, destination)
    if action == "optimize": return optimize(project_id)
    if action == "restore-branch":
        if not extra: return subprocess.CompletedProcess([], 2, stdout="[FAIL] restore-branch requires a ForgeGit branch name.\n")
        return restore_branch(project_root, project_id, extra[0], extra[1] if len(extra) > 1 else "")
    raise ValueError(action)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="ForgeGit local source-control authority")
    ap.add_argument("action", choices=("status", "ensure", "push", "history", "branches", "create-branch", "switch-branch", "rename-branch", "delete-branch", "merge-branch", "recovery-branch", "verify", "export-bundle", "optimize", "restore-branch"))
    ap.add_argument("--root", required=True)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("extra", nargs="*")
    ns = ap.parse_args(argv)
    cp = command(Path(ns.root), ns.project_id, ns.action, *ns.extra)
    print(cp.stdout, end="")
    return int(cp.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
