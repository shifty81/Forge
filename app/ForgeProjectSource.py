#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any, Sequence

from VaultSettings import load_settings

FORGE_PROJECT_SOURCE_VERSION = "FORGE-PROJECT-SOURCE-0.4.8-IDENTITY"


def _startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
    info.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
    return info


def _creationflags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0


def _run(argv: Sequence[str], *, cwd: Path | None = None, timeout: float = 300.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=_creationflags(),
        startupinfo=_startupinfo(),
    )


def git_binary() -> str:
    configured = str(((load_settings().get("sourceControl") or {}).get("gitBinary") or "")).strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path.resolve())
    return shutil.which("git") or "git"


def normalize_github_repo(value: str) -> tuple[str, str]:
    """Canonical GitHub clone/web URLs; reject ambiguous paths and URL credentials."""
    raw = value.strip()
    if raw.startswith("git@github.com:"):
        slug = raw.split(":", 1)[1]
    elif "://" in raw:
        parsed = urlsplit(raw)
        if (parsed.scheme.lower() != "https" or parsed.hostname != "github.com"
                or parsed.username is not None or parsed.password is not None
                or parsed.port is not None or parsed.query or parsed.fragment):
            raise ValueError("GitHub URL must be https://github.com/OWNER/REPO")
        slug = parsed.path.strip("/")
    else:
        slug = raw
    if slug.endswith(".git"):
        slug = slug[:-4]
    parts = slug.split("/")
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise ValueError("Use a GitHub repository URL or owner/repository slug")
    if any(part in {".", ".."} or part.endswith(".") or part.endswith(" ") for part in parts):
        raise ValueError("Ambiguous GitHub repository path")
    if any(part.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1,10)), *(f"LPT{i}" for i in range(1,10))} for part in parts):
        raise ValueError("Repository name is a reserved Windows directory")
    owner, repo = parts
    return f"https://github.com/{owner}/{repo}.git", f"https://github.com/{owner}/{repo}"


def matching_local_remote(root: Path, requested_web_url: str) -> str:
    """Return matching Git remote name; never trust only declared project metadata."""
    if not (root / ".git").exists():
        return ""
    cp = _run([git_binary(), "-C", str(root), "remote", "-v"], cwd=root, timeout=20)
    if cp.returncode != 0:
        return ""
    for line in cp.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            _, actual_web = normalize_github_repo(parts[1])
        except ValueError:
            continue
        if actual_web.casefold() == requested_web_url.casefold():
            return parts[0]
    return ""


def planned_clone_destination(repo: str, projects_root: Path) -> Path:
    """Owner-qualified destination prevents identically named repos from colliding."""
    _, web = normalize_github_repo(repo)
    owner, name = web.removeprefix("https://github.com/").split("/")
    return projects_root.expanduser().resolve() / owner / name


def github_web_url_from_remote(value: str) -> str:
    try:
        return normalize_github_repo(value)[1]
    except ValueError:
        return ""


def repo_leaf(value: str) -> str:
    clone_url, _ = normalize_github_repo(value)
    leaf = clone_url.rstrip("/").rsplit("/", 1)[-1]
    return leaf[:-4] if leaf.endswith(".git") else leaf



def declared_project_github(root: Path) -> dict[str, str]:
    """Read a repository hint from project.control.json without requiring Git to exist.

    Accepted shapes intentionally cover both snake_case and camelCase contracts so
    project adapters can opt in without depending on Forge implementation details.
    """
    root = root.expanduser().resolve()
    path = root / "project.control.json"
    if not path.is_file():
        return {"remote": "", "cloneUrl": "", "webUrl": ""}
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"remote": "", "cloneUrl": "", "webUrl": ""}
    blocks = []
    for key in ("sourceControl", "source_control"):
        block = data.get(key) if isinstance(data, dict) else None
        if isinstance(block, dict):
            blocks.append(block)
    candidates: list[str] = []
    remote_name = ""
    for block in blocks:
        remote_name = remote_name or str(block.get("defaultGitHubRemote") or block.get("default_github_remote") or "").strip()
        gh = block.get("github")
        if isinstance(gh, str):
            candidates.append(gh)
        elif isinstance(gh, dict):
            remote_name = remote_name or str(gh.get("remote") or gh.get("name") or "").strip()
            for key in ("cloneUrl", "clone_url", "webUrl", "web_url", "url", "repository"):
                value = str(gh.get(key) or "").strip()
                if value:
                    candidates.append(value)
        for key in ("githubUrl", "github_url", "repositoryUrl", "repository_url"):
            value = str(block.get(key) or "").strip()
            if value:
                candidates.append(value)
    for value in candidates:
        try:
            clone, web = normalize_github_repo(value)
            return {"remote": remote_name or "origin", "cloneUrl": clone, "webUrl": web}
        except ValueError:
            continue
    return {"remote": "", "cloneUrl": "", "webUrl": ""}

def project_github(root: Path) -> dict[str, str]:
    root = root.expanduser().resolve()
    declared = declared_project_github(root)
    if not (root / ".git").exists():
        return declared
    cp = _run([git_binary(), "-C", str(root), "remote", "-v"], cwd=root, timeout=20)
    if cp.returncode != 0:
        return declared
    seen: set[tuple[str, str]] = set()
    rows: list[tuple[str, str]] = []
    for line in cp.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        key = (name, url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(key)
    rows.sort(key=lambda item: (0 if item[0] in {"origin", "github"} else 1, item[0]))
    for name, url in rows:
        web = github_web_url_from_remote(url)
        if web:
            clone, _ = normalize_github_repo(url)
            return {"remote": name, "cloneUrl": clone, "webUrl": web}
    return declared


def clone_repository(repo: str, *, destination: Path | None = None, projects_root: Path | None = None) -> dict[str, Any]:
    """Explicit clone; preserve existing matching checkouts and refuse identity collisions."""
    clone_url, web_url = normalize_github_repo(repo)
    cfg = load_settings()
    root = (projects_root or Path(str(cfg.get("projectsRoot") or Path.home() / "Projects"))).expanduser().resolve()
    # Legacy flat clones can be reused only if the real Git remote agrees.
    legacy = root / repo_leaf(repo)
    if destination is None and legacy.exists() and (legacy / ".git").exists():
        match = matching_local_remote(legacy, web_url)
        if match:
            return {"root": str(legacy), "cloneUrl": clone_url, "webUrl": web_url,
                    "remote": match, "alreadyPresent": True,
                    "output": "Existing legacy-layout Git checkout verified and reused."}
    raw_target = destination.expanduser() if destination is not None else planned_clone_destination(repo, root)
    if raw_target.is_symlink():
        raise RuntimeError(f"Clone destination is a symlink: {raw_target}")
    target = raw_target.resolve()
    if target.exists():
        if (target / ".git").exists():
            match = matching_local_remote(target, web_url)
            if not match:
                raise RuntimeError(f"Existing Git checkout has no matching GitHub remote: {target}; review instead of reusing")
            return {"root": str(target), "cloneUrl": clone_url, "webUrl": web_url,
                    "remote": match, "alreadyPresent": True,
                    "output": "Existing Git checkout identity verified and reused."}
        if not target.is_dir() or any(target.iterdir()):
            raise RuntimeError(f"Destination already exists and is not an empty directory: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    cp = _run([git_binary(), "clone", "--origin", "origin", clone_url, str(target)], cwd=target.parent, timeout=1800)
    if cp.returncode != 0:
        raise RuntimeError(cp.stdout.strip() or f"git clone exited {cp.returncode}")
    # Verify newly created checkout identity, not merely the git process exit status.
    match = matching_local_remote(target, web_url)
    if not match:
        raise RuntimeError(f"Clone reported success but GitHub remote identity cannot be verified: {target}")
    return {"root": str(target), "cloneUrl": clone_url, "webUrl": web_url,
            "remote": match, "alreadyPresent": False, "output": cp.stdout.strip()}


def pull_project(root: Path) -> subprocess.CompletedProcess[str]:
    root = root.expanduser().resolve()
    return _run([git_binary(), "-C", str(root), "pull", "--ff-only"], cwd=root, timeout=600)
