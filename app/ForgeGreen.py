#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, os, shutil, subprocess, threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from VaultPaths import ensure_artifact_project_tree
from ForgePackagePolicy import is_governed

FORGE_GREEN_VERSION = "FORGE-GREEN-0.5-F620"
_GREEN_CACHE_LOCK = threading.Lock()
_GREEN_CACHE: dict[str, tuple[tuple[object, ...], str, int]] = {}


def _git_binary() -> str:
    try:
        from ForgeStatusCache import git_binary
        value = git_binary()
        if value:
            return value
    except Exception:
        pass
    return shutil.which("git") or ""


def _quiet_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
    info.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
    return info


def _quiet_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0


def _git_probe(root: Path, *args: str, timeout: float = 20.0, binary: bool = False) -> subprocess.CompletedProcess:
    git = _git_binary()
    if not git:
        return subprocess.CompletedProcess([], 127, stdout=b"" if binary else "")
    return subprocess.run(
        [git, "-C", str(root), *args], cwd=str(root),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=not binary, encoding=None if binary else "utf-8", errors=None if binary else "replace",
        timeout=timeout, check=False, creationflags=_quiet_flags(), startupinfo=_quiet_startupinfo(),
    )


def _project_id(root: Path) -> str:
    path = root / "project.control.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            project = (data.get("project") or {}) if isinstance(data, dict) else {}
            value = str(project.get("id") or "").strip()
            if value:
                return value
        except Exception:
            pass
    return root.name.lower().replace(" ", "-") or "project"


def marker_path(root: Path) -> Path:
    root = root.expanduser().resolve()
    reports = ensure_artifact_project_tree(_project_id(root))["reports"] / "source-control"
    reports.mkdir(parents=True, exist_ok=True)
    return reports / "last-green-quality-gate.json"


def _green_cache_token(root: Path, marker: Path) -> tuple[object, ...]:
    try:
        marker_mtime = marker.stat().st_mtime_ns
    except OSError:
        marker_mtime = 0
    if not (root / ".git").exists() or not _git_binary():
        return (marker_mtime, object())
    try:
        status = _git_probe(root, "status", "--porcelain=v1", "--untracked-files=all", "-z", timeout=30, binary=True)
        head = _git_probe(root, "rev-parse", "HEAD", timeout=15)
    except Exception:
        return (marker_mtime, object())
    raw = status.stdout if isinstance(status.stdout, (bytes, bytearray)) else b""
    governed_stats: list[tuple[bytes, int, int]] = []
    for record in bytes(raw).split(b"\0"):
        if not record:
            continue
        candidate = record[3:] if len(record) >= 4 and record[2:3] == b" " else record
        if not candidate:
            continue
        try:
            rel = candidate.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        except Exception:
            continue
        if not is_governed(rel):
            continue
        try:
            st = (root / rel).stat()
            governed_stats.append((candidate, int(st.st_mtime_ns), int(st.st_size)))
        except OSError:
            governed_stats.append((candidate, 0, 0))
    return (
        marker_mtime, status.returncode, tuple(governed_stats),
        head.returncode, head.stdout if isinstance(head.stdout, str) else b"",
    )


def _git_file_list(root: Path) -> list[Path] | None:
    if not _git_binary() or not (root / ".git").exists():
        return None
    try:
        cp = _git_probe(root, "ls-files", "-co", "--exclude-standard", "-z", timeout=60, binary=True)
    except Exception:
        return None
    if cp.returncode != 0:
        return None
    out: list[Path] = []
    for raw in cp.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        if not is_governed(rel):
            continue
        path = root / rel
        if path.is_file():
            out.append(path)
    return out


def _walk_file_list(root: Path) -> list[Path]:
    skip_anywhere = {
        ".git", "__pycache__", "target", "build", "builds", "bin", "obj", "node_modules",
        ".venv", "venv", ".cache", ".pytest_cache", ".idea", ".vs", "artifacts", "logs",
    }
    out: list[Path] = []
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        kept = []
        for d in dirs:
            rel = (current_path / d).relative_to(root).as_posix()
            if d.casefold() in skip_anywhere or not is_governed(rel):
                continue
            kept.append(d)
        dirs[:] = kept
        for name in files:
            path = current_path / name
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if is_governed(rel) and path.is_file():
                out.append(path)
    return out


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def governed_source_fingerprint(root: Path) -> tuple[str, int]:
    root = root.expanduser().resolve()
    files = _git_file_list(root)
    if files is None:
        files = _walk_file_list(root)
    h = hashlib.sha256()
    count = 0
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix().casefold()):
        try:
            rel = path.relative_to(root).as_posix()
            if not is_governed(rel):
                continue
            size = path.stat().st_size
            digest = _file_sha256(path)
        except (OSError, ValueError):
            continue
        h.update(f"{rel}\t{size}\t{digest}\n".encode("utf-8", errors="surrogateescape"))
        count += 1
    return h.hexdigest(), count


def _git_text(root: Path, *args: str) -> str:
    if not _git_binary() or not (root / ".git").exists():
        return ""
    try:
        cp = _git_probe(root, *args, timeout=15)
        return cp.stdout.strip() if cp.returncode == 0 and isinstance(cp.stdout, str) else ""
    except Exception:
        return ""


def certify_green(root: Path, *, gate: str = "full") -> dict[str, Any]:
    root = root.expanduser().resolve()
    fingerprint, count = governed_source_fingerprint(root)
    payload = {
        "schema": "forge.green_quality_gate.v1",
        "version": FORGE_GREEN_VERSION,
        "projectId": _project_id(root),
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "result": "GREEN",
        "gate": gate,
        "sourceFingerprint": fingerprint,
        "sourceFileCount": count,
        "gitHeadAtGate": _git_text(root, "rev-parse", "HEAD"),
        "gitBranchAtGate": _git_text(root, "branch", "--show-current"),
    }
    path = marker_path(root)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)
    payload["path"] = str(path)
    try:
        token = _green_cache_token(root, path)
        with _GREEN_CACHE_LOCK:
            _GREEN_CACHE[os.path.normcase(str(root))] = (token, fingerprint, count)
    except Exception:
        pass
    return payload


def read_green(root: Path) -> dict[str, Any] | None:
    path = marker_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def green_status(root: Path) -> tuple[bool, bool, str, dict[str, Any] | None]:
    root = root.expanduser().resolve()
    path = marker_path(root)
    data = read_green(root)
    if not data:
        return False, False, str(path), None
    result = str(data.get("result") or data.get("status") or "").upper()
    marker = result in {"PASS", "GREEN", "OK", "SUCCESS"}
    expected = str(data.get("sourceFingerprint") or "").strip().lower()
    if not marker or not expected:
        return marker, False, str(path), data
    key = os.path.normcase(str(root))
    token = _green_cache_token(root, path)
    with _GREEN_CACHE_LOCK:
        cached = _GREEN_CACHE.get(key)
    if cached is not None and cached[0] == token:
        current = cached[1]
    else:
        current, count = governed_source_fingerprint(root)
        with _GREEN_CACHE_LOCK:
            _GREEN_CACHE[key] = (token, current, count)
    return marker, current.lower() == expected, str(path), data
