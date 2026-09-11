#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from ForgeProjectSource import declared_project_github, normalize_github_repo
from ForgePYSettings import load_settings

FORGE_SOURCE_VERSION = "FORGEPY-SOURCE-0.4.44"


def _git_exe() -> str:
    configured = str(((load_settings().get("sourceControl") or {}).get("gitBinary") or "")).strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path.resolve())
    return shutil.which("git") or "git"


def _startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
    info.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
    return info


def _run(root: Path, *args: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_git_exe(), "-C", str(root), *args], cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, check=False,
        creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0,
        startupinfo=_startupinfo(),
    )


def _completed(output: str, rc: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], rc, stdout=output)


def _remote_kind(name: str, url: str) -> str:
    low_name = name.casefold(); low = url.casefold()
    if "github.com" in low:
        return "github"
    sc = load_settings().get("sourceControl") or {}
    forgegit_names = {
        str(sc.get("defaultForgeGitRemote") or "forgegit").strip().casefold(),
        str(sc.get("defaultInternalGitRemote") or "forgepy-internal").strip().casefold(),
        "forgegit", "forgepy-internal",
    }
    if low_name in forgegit_names:
        return "forgegit"
    roots = [str(sc.get("forgeGitRoot") or "").strip(), str(sc.get("internalGitRoot") or "").strip()]
    for raw_root in roots:
        if not raw_root:
            continue
        try:
            remote_path = Path(url).expanduser().resolve()
            if remote_path.is_relative_to(Path(raw_root).expanduser().resolve()):
                return "forgegit"
        except Exception:
            pass
    hosts = {x.strip().casefold() for x in str(os.environ.get("VAULT_FORGEJO_HOSTS") or "").split(";") if x.strip()}
    if "forgejo" in low_name or "forgejo" in low:
        return "forgejo"
    if any(token in low for token in ("localhost", "127.0.0.1", "::1")):
        return "forgejo"
    if any(host in low for host in hosts):
        return "forgejo"
    return "other"


def _remote_rows(root: Path) -> list[dict[str, str]]:
    cp = _run(root, "remote", "-v")
    if cp.returncode != 0:
        return []
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    pattern = re.compile(r"^(\S+)\s+(\S+)\s+\((fetch|push)\)$")
    for line in cp.stdout.splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        name, url, direction = m.groups()
        key = (name, url, direction)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"name": name, "url": url, "direction": direction, "kind": _remote_kind(name, url)})
    return rows


def _has_head(root: Path) -> bool:
    return _run(root, "rev-parse", "--verify", "HEAD", timeout=15).returncode == 0


def _branch(root: Path, fallback: str = "main") -> str:
    cp = _run(root, "branch", "--show-current", timeout=15)
    value = cp.stdout.strip() if cp.returncode == 0 else ""
    if value:
        return value
    symbolic = _run(root, "symbolic-ref", "--short", "HEAD", timeout=15)
    value = symbolic.stdout.strip() if symbolic.returncode == 0 else ""
    return value or fallback


def _default_remote_name(kind: str) -> str:
    sc = load_settings().get("sourceControl") or {}
    if kind == "github":
        return str(sc.get("defaultGitHubRemote") or "origin").strip() or "origin"
    if kind in {"forgegit", "internal"}:
        return str(sc.get("defaultForgeGitRemote") or sc.get("defaultInternalGitRemote") or "forgegit").strip() or "forgegit"
    return str(sc.get("defaultForgejoRemote") or "forgejo").strip() or "forgejo"


def remote_names(root: Path, kind: str) -> list[str]:
    return sorted({x["name"] for x in _remote_rows(root) if x["kind"] == kind})


def status(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    ready = bool(shutil.which("git") or Path(_git_exe()).exists()) and (root / ".git").exists()
    out: dict[str, Any] = {
        "schema": "forge.source.status.v2", "version": FORGE_SOURCE_VERSION,
        "gitReady": ready, "hasHead": False, "branch": "", "head": "", "headShort": "", "clean": False,
        "staged": 0, "unstaged": 0, "untracked": 0, "ahead": None, "behind": None,
        "upstream": "", "remotes": [], "githubConfigured": False, "forgeGitConfigured": False, "internalGitConfigured": False, "forgejoConfigured": False,
        "githubDeclared": False, "githubDeclaredUrl": "",
    }
    declared = declared_project_github(root)
    if declared.get("cloneUrl"):
        out["githubDeclared"] = True
        out["githubDeclaredUrl"] = str(declared.get("cloneUrl") or "")
    if not ready:
        return out
    cp = _run(root, "status", "--porcelain=v1", "--untracked-files=all")
    lines = [line for line in cp.stdout.splitlines() if line]
    staged = unstaged = untracked = 0
    for line in lines:
        code = line[:2] if len(line) >= 2 else "  "
        if code == "??":
            untracked += 1; continue
        if code[0] not in {" ", "?"}: staged += 1
        if code[1] not in {" ", "?"}: unstaged += 1
    out.update(clean=(cp.returncode == 0 and not lines), staged=staged, unstaged=unstaged, untracked=untracked)
    out["hasHead"] = _has_head(root)
    out["branch"] = _branch(root, "main")
    if out["hasHead"]:
        head = _run(root, "rev-parse", "HEAD")
        if head.returncode == 0:
            out["head"] = head.stdout.strip(); out["headShort"] = head.stdout.strip()[:12]
        upstream = _run(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
        if upstream.returncode == 0:
            out["upstream"] = upstream.stdout.strip()
            counts = _run(root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
            if counts.returncode == 0:
                parts = counts.stdout.split()
                if len(parts) == 2 and all(x.isdigit() for x in parts):
                    out["ahead"], out["behind"] = int(parts[0]), int(parts[1])
    remotes = _remote_rows(root); out["remotes"] = remotes
    out["githubConfigured"] = any(x["kind"] == "github" for x in remotes)
    out["forgeGitConfigured"] = any(x["kind"] == "forgegit" for x in remotes)
    out["internalGitConfigured"] = out["forgeGitConfigured"]  # compatibility key
    out["forgejoConfigured"] = any(x["kind"] == "forgejo" for x in remotes)
    return out


def _ensure_github_remote(root: Path, hint: str = "") -> tuple[str, list[str], bool]:
    """Return (remote_name, messages, created). Never rewrites an existing GitHub remote."""
    messages: list[str] = []
    names = remote_names(root, "github")
    if names:
        return names[0], messages, False
    declared = declared_project_github(root)
    raw = hint.strip() or str(declared.get("cloneUrl") or declared.get("webUrl") or "").strip()
    if not raw:
        return "", messages, False
    try:
        clone_url, _ = normalize_github_repo(raw)
    except ValueError as exc:
        messages.append(f"[WARN] Declared GitHub repository is invalid: {exc}")
        return "", messages, False
    name = str(declared.get("remote") or _default_remote_name("github") or "origin").strip() or "origin"
    existing_names = {x["name"] for x in _remote_rows(root)}
    if name in existing_names:
        # Do not silently rewrite a same-name non-GitHub remote. Pick a deterministic alternate.
        name = "github" if "github" not in existing_names else "github-upstream"
    cp = _run(root, "remote", "add", name, clone_url)
    if cp.returncode != 0:
        messages.append(cp.stdout.rstrip())
        return "", messages, False
    messages.append(f"[PASS] Configured GitHub remote {name}: {clone_url}")
    return name, messages, True


def _adopt_remote_history_if_unborn(root: Path, remote: str, branch: str) -> tuple[list[str], bool]:
    messages: list[str] = []
    if not remote or _has_head(root):
        return messages, False
    fetch = _run(root, "fetch", remote, branch, timeout=300)
    if fetch.returncode != 0:
        messages.append(f"[WARN] GitHub remote configured, but fetch {remote}/{branch} did not complete:\n{fetch.stdout.rstrip()}")
        return messages, False
    remote_ref = f"refs/remotes/{remote}/{branch}"
    verify = _run(root, "show-ref", "--verify", "--quiet", remote_ref)
    if verify.returncode != 0:
        messages.append(f"[INFO] Remote {remote} has no {branch} history yet; local repository remains at its first commit stage.")
        return messages, False
    # reset --mixed changes HEAD/index to the remote history while preserving every working-tree byte.
    # This is the safe adoption path for an existing source folder whose .git directory is unborn.
    reset = _run(root, "reset", "--mixed", f"{remote}/{branch}")
    if reset.returncode != 0:
        messages.append(f"[WARN] Remote history fetched but could not be adopted safely:\n{reset.stdout.rstrip()}")
        return messages, False
    _run(root, "branch", "--set-upstream-to", f"{remote}/{branch}", branch)
    messages.append(
        f"[PASS] Adopted {remote}/{branch} as local parent history without replacing working-tree files.\n"
        "[INFO] Current Forge/project files remain in place and now appear as the reviewable replacement diff."
    )
    return messages, True


def initialize_repository(root: Path, branch: str = "main", github_hint: str = "") -> subprocess.CompletedProcess[str]:
    root = root.expanduser().resolve()
    output: list[str] = []
    if not (root / ".git").exists():
        init = _run(root, "init", "-b", branch)
        output.append(init.stdout.rstrip())
        if init.returncode != 0:
            return _completed("\n".join(x for x in output if x) + "\n", init.returncode)
    else:
        output.append("[PASS] Existing Git metadata detected; source initialization will normalize authority without deleting it.")

    if not _has_head(root):
        current = _branch(root, branch)
        if current != branch:
            symbolic = _run(root, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
            if symbolic.returncode == 0:
                output.append(f"[PASS] Unborn branch normalized to {branch}.")

    remote, messages, _ = _ensure_github_remote(root, github_hint)
    output.extend(messages)
    adopted_messages, _ = _adopt_remote_history_if_unborn(root, remote, branch)
    output.extend(adopted_messages)
    if not remote:
        output.append("[INFO] No GitHub repository is declared/configured yet. Use Configure Remote or clone onboarding to bind one.")
    return _completed("\n".join(x for x in output if x) + "\n", 0)


def _review(root: Path, *, full: bool = False) -> subprocess.CompletedProcess[str]:
    if not (root / ".git").exists():
        return _completed("[FAIL] Git repository is not initialized.\n", 2)
    has_head = _has_head(root)
    output: list[str] = []
    st = _run(root, "status", "--short", "--branch")
    output.append(st.stdout.rstrip())
    if has_head:
        cp = _run(root, "diff", "HEAD") if full else _run(root, "diff", "--stat", "HEAD")
        if cp.stdout.strip():
            output.append(cp.stdout.rstrip())
        return _completed("\n".join(x for x in output if x) + "\n", cp.returncode)
    output.insert(0, "[INFO] Repository has no local commit yet; review is showing staged/untracked first-commit content instead of diffing an invalid HEAD.")
    cached = _run(root, "diff", "--cached" if full else "--cached", *( [] if full else ["--stat"] ))
    if cached.stdout.strip():
        output.append(cached.stdout.rstrip())
    return _completed("\n".join(x for x in output if x) + "\n", 0)


def repository_tree(root: Path, limit: int = 5000) -> list[dict[str, Any]]:
    """Return a compact IDE-style repository tree model with Git state per path."""
    root = root.expanduser().resolve()
    if not (root / ".git").exists():
        return []
    status_cp = _run(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", timeout=30)
    statuses: dict[str, str] = {}
    raw = status_cp.stdout or ""
    records = raw.split("\x00")
    i = 0
    while i < len(records):
        rec = records[i]
        i += 1
        if not rec or len(rec) < 3:
            continue
        code = rec[:2]
        path = rec[3:]
        if code[0] in {"R", "C"} and i < len(records) and records[i]:
            path = records[i]
            i += 1
        statuses[path.replace("\\", "/")] = code
    cp = _run(root, "ls-files", "-co", "--exclude-standard", "-z", timeout=60)
    if cp.returncode != 0:
        return []
    paths = [x for x in (cp.stdout or "").split("\x00") if x]
    rows: list[dict[str, Any]] = []
    for rel in paths[:max(1, int(limit))]:
        rel = rel.replace("\\", "/")
        rows.append({
            "path": rel,
            "name": Path(rel).name,
            "parent": Path(rel).parent.as_posix() if Path(rel).parent.as_posix() != "." else "",
            "status": statuses.get(rel, "  "),
            "changed": rel in statuses,
        })
    return rows


def branch_graph(root: Path, limit: int = 120) -> str:
    root = root.expanduser().resolve()
    if not _has_head(root):
        return "Repository has no commits yet.\n"
    fmt = "%C(auto)%h%Creset %d %s %C(dim white)(%cr)%Creset"
    cp = _run(root, "log", "--graph", "--decorate", "--all", f"--max-count={max(1, int(limit))}", f"--pretty=format:{fmt}", timeout=60)
    return cp.stdout if cp.returncode == 0 else cp.stdout


def list_tags(root: Path) -> list[dict[str, str]]:
    cp = _run(root, "for-each-ref", "--sort=-creatordate", "--format=%(refname:short)|%(objectname:short)|%(creatordate:iso8601-strict)|%(subject)", "refs/tags", timeout=30)
    rows: list[dict[str, str]] = []
    if cp.returncode != 0:
        return rows
    for line in cp.stdout.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            rows.append(dict(zip(("name","head","created","subject"), parts)))
    return rows




def authority_matrix(root: Path, project_id: str = "") -> dict[str, Any]:
    """Compare the current commit across Working Tree, ForgeGit and GitHub."""
    root = root.expanduser().resolve()
    branch = _branch(root, "main")
    head_cp = _run(root, "rev-parse", "HEAD", timeout=15) if _has_head(root) else _completed("")
    head = head_cp.stdout.strip() if head_cp.returncode == 0 else ""
    result: dict[str, Any] = {"branch": branch, "workingHead": head, "forgeGitHead": "", "github": [], "allPrimaryMatch": False}
    try:
        from ForgeGit import repository_path
        repo = repository_path(project_id or _project_id(root))
        if (repo / "HEAD").is_file():
            cp = subprocess.run([shutil.which("git") or "git", "--git-dir", str(repo), "rev-parse", f"refs/heads/{branch}"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", check=False, creationflags=_quiet_flags(), startupinfo=_quiet_startupinfo())
            if cp.returncode == 0:
                result["forgeGitHead"] = cp.stdout.strip()
    except Exception:
        pass
    for name in remote_names(root, "github"):
        cp = _run(root, "ls-remote", name, f"refs/heads/{branch}", timeout=60)
        remote_head = ""
        if cp.returncode == 0 and cp.stdout.strip():
            remote_head = cp.stdout.split()[0].strip()
        result["github"].append({"remote": name, "head": remote_head, "matchesWorking": bool(head and remote_head == head)})
    github_match = all(bool(row.get("matchesWorking")) for row in result["github"]) if result["github"] else False
    result["allPrimaryMatch"] = bool(head and result["forgeGitHead"] == head and (github_match or not result["github"]))
    return result


def repair_authority(root: Path, project_id: str, github_hint: str = "") -> subprocess.CompletedProcess[str]:
    """Recover source metadata after folder replacement without replacing source files."""
    init = initialize_repository(root, "main", github_hint)
    output = ["=== WORKING GIT / GITHUB ===\n" + init.stdout]
    if init.returncode != 0:
        return _completed("".join(output), init.returncode)
    try:
        from ForgeGit import ensure
        fg = ensure(root, project_id or _project_id(root))
        output.append("=== FORGEGIT ===\n" + fg.stdout)
        rc = fg.returncode
    except Exception as exc:
        output.append(f"[WARN] Working source authority recovered, but ForgeGit bind failed: {exc}\n")
        rc = 1
    return _completed("".join(output), rc)

def _project_id(root: Path, fallback: str = "") -> str:
    path = root / "project.control.json"
    if path.is_file():
        try:
            import json
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            value = str(((data.get("project") or {}) if isinstance(data, dict) else {}).get("id") or "").strip()
            if value:
                return value
        except Exception:
            pass
    return fallback or root.name.casefold().replace(" ", "-")


def commit_green(root: Path, project_id: str, message: str) -> subprocess.CompletedProcess[str]:
    """Universal GREEN-protected commit usable by every registered Git project."""
    from ForgeGreen import green_status
    root = root.expanduser().resolve()
    if not (root / ".git").exists():
        return _completed("[FAIL] Git repository is not initialized.\n", 2)
    marker, matches, marker_path, _ = green_status(root)
    if not marker:
        return _completed(f"[FAIL] No certified GREEN gate exists for this source.\n[INFO] GREEN marker: {marker_path}\n", 2)
    if not matches:
        return _completed("[FAIL] Source has changed since the last GREEN Full Gate. Run Full Gate / Certify GREEN before committing.\n", 2)
    add = _run(root, "add", "-A", timeout=120)
    if add.returncode != 0:
        return add
    changed = _run(root, "diff", "--cached", "--quiet", timeout=30)
    if changed.returncode == 0:
        head = _run(root, "rev-parse", "--short", "HEAD", timeout=15)
        return _completed(f"[PASS] No source changes to commit; certified GREEN source is already committed at {head.stdout.strip() or '<no head>'}.\n", 0)
    msg = str(message or "").strip() or "Certified GREEN"
    cp = _run(root, "commit", "-m", msg, timeout=300)
    if cp.returncode == 0:
        cp.stdout = "[PASS] Committed certified GREEN source.\n" + cp.stdout
        try:
            from ForgeSourceReceipts import write_receipt
            receipt = write_receipt(project_id, "commit-green", {
                "head": _run(root, "rev-parse", "HEAD", timeout=15).stdout.strip(),
                "branch": _branch(root, "main"),
                "message": msg,
            })
            cp.stdout += f"[PASS] Source-control receipt: {receipt}\n"
        except Exception as exc:
            cp.stdout += f"[WARN] Commit succeeded but source receipt could not be written: {exc}\n"
    return cp


def commit_push_green(root: Path, project_id: str, message: str) -> subprocess.CompletedProcess[str]:
    """Commit one GREEN state, snapshot it to ForgeGit, then push GitHub when configured."""
    commit = commit_green(root, project_id, message)
    if commit.returncode != 0:
        return commit
    output = [commit.stdout]
    rc = 0
    from ForgeGit import push_snapshot
    fg = push_snapshot(root, project_id)
    output.append("=== FORGEGIT ===\n" + fg.stdout)
    if fg.returncode != 0:
        rc = fg.returncode
    names = remote_names(root, "github")
    if not names:
        output.append("[WARN] GitHub is not configured; GREEN commit is preserved locally and in ForgeGit.\n")
    else:
        branch = _branch(root, "main")
        for name in names:
            cp = _run(root, "push", name, f"HEAD:{branch}", timeout=300)
            output.append(f"=== GITHUB remote {name} ===\n{cp.stdout}")
            if cp.returncode != 0:
                rc = cp.returncode
    try:
        from ForgeSourceReceipts import write_receipt
        receipt = write_receipt(project_id, "commit-push-green", {
            "head": _run(root, "rev-parse", "HEAD", timeout=15).stdout.strip(),
            "branch": _branch(root, "main"),
            "forgeGitReturnCode": int(fg.returncode),
            "githubConfigured": bool(names),
            "result": "PASS" if rc == 0 else "WARN",
        })
        output.append(f"[PASS] Source-control receipt: {receipt}\n")
    except Exception as exc:
        output.append(f"[WARN] Source-control receipt could not be written: {exc}\n")
    return _completed("".join(output), rc)


def _stage_paths(root: Path, paths: Sequence[str]) -> subprocess.CompletedProcess[str]:
    if not paths:
        return _completed("[FAIL] No paths selected.\n", 2)
    return _run(root, "add", "--", *paths, timeout=120)


def _unstage_paths(root: Path, paths: Sequence[str]) -> subprocess.CompletedProcess[str]:
    if not paths:
        return _completed("[FAIL] No paths selected.\n", 2)
    if _has_head(root):
        return _run(root, "restore", "--staged", "--", *paths, timeout=120)
    return _run(root, "rm", "--cached", "--ignore-unmatch", "--", *paths, timeout=120)


def _discard_paths(root: Path, paths: Sequence[str]) -> subprocess.CompletedProcess[str]:
    if not paths:
        return _completed("[FAIL] No paths selected.\n", 2)
    # Never delete untracked files from a generic discard action. Tracked changes only.
    tracked: list[str] = []
    skipped: list[str] = []
    for rel in paths:
        cp = _run(root, "ls-files", "--error-unmatch", "--", rel, timeout=15)
        (tracked if cp.returncode == 0 else skipped).append(rel)
    output: list[str] = []
    rc = 0
    if tracked:
        cp = _run(root, "restore", "--worktree", "--staged", "--", *tracked, timeout=120)
        output.append(cp.stdout)
        rc = cp.returncode
    if skipped:
        output.append("[WARN] Untracked paths were not deleted by Discard: " + ", ".join(skipped) + "\n")
    return _completed("".join(output) or "[PASS] Selected tracked changes discarded.\n", rc)


def command(root: Path, action: str, *extra: str) -> subprocess.CompletedProcess[str]:
    root = root.expanduser().resolve()
    action = action.casefold()
    if action == "commit-green":
        project_id = extra[0] if extra else _project_id(root)
        message = extra[1] if len(extra) > 1 else "Certified GREEN"
        return commit_green(root, project_id, message)
    if action == "commit-push-green":
        project_id = extra[0] if extra else _project_id(root)
        message = extra[1] if len(extra) > 1 else "Certified GREEN"
        return commit_push_green(root, project_id, message)
    if action == "tree-json":
        import json
        limit = int(extra[0]) if extra and str(extra[0]).isdigit() else 5000
        return _completed(json.dumps(repository_tree(root, limit), indent=2) + "\n")
    if action == "graph":
        limit = int(extra[0]) if extra and str(extra[0]).isdigit() else 120
        return _completed(branch_graph(root, limit))
    if action == "stage":
        return _stage_paths(root, extra)
    if action == "unstage":
        return _unstage_paths(root, extra)
    if action == "discard":
        return _discard_paths(root, extra)
    if action == "diff-file":
        if not extra: return _completed("[FAIL] diff-file requires a path.\n", 2)
        return _run(root, "diff", "--", extra[0], timeout=60)
    if action == "create-branch":
        from ForgeGit import create_branch
        if not extra: return _completed("[FAIL] create-branch requires a name.\n", 2)
        return create_branch(root, extra[0], extra[1] if len(extra) > 1 else "HEAD", switch=True)
    if action == "switch-branch":
        from ForgeGit import switch_branch
        if not extra: return _completed("[FAIL] switch-branch requires a name.\n", 2)
        return switch_branch(root, extra[0])
    if action == "rename-branch":
        from ForgeGit import rename_branch
        if len(extra) < 2: return _completed("[FAIL] rename-branch requires OLD NEW.\n", 2)
        return rename_branch(root, extra[0], extra[1])
    if action == "delete-branch":
        from ForgeGit import delete_branch
        if not extra: return _completed("[FAIL] delete-branch requires a name.\n", 2)
        return delete_branch(root, extra[0], force="--force" in extra[1:])
    if action == "merge-branch":
        from ForgeGit import merge_branch
        if not extra: return _completed("[FAIL] merge-branch requires a name.\n", 2)
        return merge_branch(root, extra[0])
    if action == "recovery-branch":
        from ForgeGit import create_recovery_branch
        return create_recovery_branch(root, extra[0] if extra else "")
    if action == "tags-json":
        import json
        return _completed(json.dumps(list_tags(root), indent=2) + "\n")
    if action == "authority-json":
        import json
        project_id = extra[0] if extra else _project_id(root)
        return _completed(json.dumps(authority_matrix(root, project_id), indent=2, sort_keys=True) + "\n")
    if action == "repair-authority":
        project_id = extra[0] if extra else _project_id(root)
        github_hint = extra[1] if len(extra) > 1 else ""
        return repair_authority(root, project_id, github_hint)
    if action == "delete-tag":
        if not extra: return _completed("[FAIL] delete-tag requires a tag name.\n", 2)
        return _run(root, "tag", "-d", extra[0], timeout=60)
    if action == "branch-from-tag":
        if len(extra) < 2: return _completed("[FAIL] branch-from-tag requires TAG BRANCH.\n", 2)
        from ForgeGit import create_branch
        return create_branch(root, extra[1], extra[0], switch=True)
    if action == "create-tag":
        if not extra: return _completed("[FAIL] create-tag requires a tag name.\n", 2)
        name = extra[0]; message = extra[1] if len(extra) > 1 else f"ForgePY tag {name}"
        return _run(root, "tag", "-a", name, "-m", message, timeout=60)
    if action == "status":
        return _run(root, "status", "--short", "--branch")
    if action == "review":
        return _review(root, full=False)
    if action == "diff":
        return _review(root, full=True)
    if action == "history":
        cp = _run(root, "log", "--oneline", "--decorate", "--graph", "--all", "-40")
        if cp.returncode != 0 and not _has_head(root):
            return _completed("[INFO] Repository has no commits yet.\n", 0)
        return cp
    if action == "branches": return _run(root, "branch", "-vv", "--all")
    if action == "remotes": return _run(root, "remote", "-v")
    if action == "fetch-all": return _run(root, "fetch", "--all", "--prune", timeout=300)
    if action == "pull-ff":
        if not _has_head(root):
            return _completed("[FAIL] No local commit exists yet. Initialize/adopt source authority first.\n", 2)
        return _run(root, "pull", "--ff-only", timeout=300)
    if action == "push":
        return push_current(root)
    if action in {"push-internal", "push-forgegit"}:
        from ForgeGit import push_snapshot
        project_id = extra[0] if extra else root.name
        return push_snapshot(root, project_id)
    if action in {"push-github", "push-forgejo"}:
        kind = action.split("-", 1)[1]
        names = remote_names(root, kind)
        if not names:
            return _completed(f"[FAIL] No {kind} remote is configured.\n", 2)
        if not _has_head(root):
            return _completed("[FAIL] No commit exists yet. Run Full Gate, then Commit + Push GREEN.\n", 2)
        branch = _branch(root, "main")
        output = []
        rc = 0
        upstream = str(status(root).get("upstream") or "")
        for name in names:
            argv = ["push", name, f"HEAD:{branch}"]
            if not upstream and len(names) == 1:
                argv = ["push", "-u", name, f"HEAD:{branch}"]
            cp = _run(root, *argv, timeout=300)
            output.append(f"=== {kind.upper()} remote {name} ===\n{cp.stdout}")
            if cp.returncode != 0: rc = cp.returncode
        return _completed("".join(output), rc)
    if action == "sync-primary":
        if not _has_head(root):
            return _completed("[FAIL] No commit exists yet. Run Full Gate, then Commit + Push GREEN.\n", 2)
        from ForgeGit import push_snapshot
        project_id = extra[0] if extra else root.name
        output = []
        rc = 0
        internal = push_snapshot(root, project_id)
        output.append("=== FORGEGIT ===\n" + internal.stdout)
        if internal.returncode != 0: rc = internal.returncode
        names = remote_names(root, "github")
        if not names:
            output.append("[WARN] No GitHub remote configured; GitHub push skipped.\n")
        else:
            branch = _branch(root, "main")
            for name in names:
                cp = _run(root, "push", name, f"HEAD:{branch}", timeout=300)
                output.append(f"=== GITHUB remote {name} ===\n{cp.stdout}")
                if cp.returncode != 0: rc = cp.returncode
        try:
            from ForgeSourceReceipts import write_receipt
            receipt = write_receipt(project_id, "sync-primary", {
                "head": _run(root, "rev-parse", "HEAD", timeout=15).stdout.strip(),
                "branch": _branch(root, "main"),
                "forgeGitReturnCode": int(internal.returncode),
                "githubRemotes": list(names),
                "returnCode": int(rc),
            })
            output.append(f"[PASS] Source-control receipt: {receipt}\n")
        except Exception as exc:
            output.append(f"[WARN] Sync succeeded but receipt could not be written: {exc}\n")
        return _completed("".join(output), rc)
    if action == "sync-both":
        if not _has_head(root):
            return _completed("[FAIL] No commit exists yet. Run Full Gate, then Commit + Push GREEN.\n", 2)
        branch = _branch(root, "main")
        output = []
        rc = 0
        for kind in ("forgejo", "github"):
            names = remote_names(root, kind)
            if not names:
                output.append(f"[WARN] No {kind} remote configured; skipped.\n")
                continue
            for name in names:
                cp = _run(root, "push", name, f"HEAD:{branch}", timeout=300)
                output.append(f"=== {kind.upper()} remote {name} ===\n{cp.stdout}")
                if cp.returncode != 0: rc = cp.returncode
        return _completed("".join(output), rc)
    if action == "init":
        branch = extra[0] if extra else "main"
        hint = extra[1] if len(extra) > 1 else ""
        return initialize_repository(root, branch, hint)
    if action == "set-remote":
        if len(extra) < 2:
            return _completed("[FAIL] set-remote requires NAME URL\n", 2)
        name, url = extra[0], extra[1]
        existing = {x["name"] for x in _remote_rows(root)}
        return _run(root, "remote", "set-url" if name in existing else "add", name, url)
    raise ValueError(f"unknown Forge source action: {action}")


def push_current(root: Path) -> subprocess.CompletedProcess[str]:
    root = root.expanduser().resolve()
    if not _has_head(root):
        return _completed("[FAIL] No commit exists yet. Run Full Gate, then Commit + Push GREEN.\n", 2)
    state = status(root)
    if state.get("upstream"):
        return _run(root, "push", timeout=300)
    branch = _branch(root, "main")
    candidates = remote_names(root, "github")
    if not candidates:
        rows = _remote_rows(root)
        if rows:
            names = []
            for row in rows:
                if row["name"] not in names:
                    names.append(row["name"])
            candidates = sorted(names, key=lambda n: (0 if n == "origin" else 1, n))
    if not candidates:
        return _completed("[FAIL] No Git remote is configured.\n", 2)
    remote = candidates[0]
    return _run(root, "push", "-u", remote, f"HEAD:{branch}", timeout=300)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="ForgePY Git / ForgeGit / GitHub authority")
    ap.add_argument("action", choices=("status-json", "status", "review", "diff", "history", "branches", "remotes", "fetch-all", "pull-ff", "push", "push-github", "push-internal", "push-forgegit", "push-forgejo", "sync-primary", "sync-both", "init", "set-remote", "commit-green", "commit-push-green", "tree-json", "graph", "stage", "unstage", "discard", "diff-file", "create-branch", "switch-branch", "rename-branch", "delete-branch", "merge-branch", "recovery-branch", "tags-json", "create-tag", "delete-tag", "branch-from-tag", "authority-json", "repair-authority"))
    ap.add_argument("--root", required=True)
    ap.add_argument("extra", nargs="*")
    ns = ap.parse_args(argv)
    root = Path(ns.root).expanduser().resolve()
    if ns.action == "status-json":
        import json
        print(json.dumps(status(root), indent=2, sort_keys=True)); return 0
    cp = command(root, ns.action, *ns.extra)
    print(cp.stdout, end="")
    return int(cp.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
