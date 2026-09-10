#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from VaultPaths import ensure_artifact_project_tree

FORGE_GREEN_VERSION = "FORGE-GREEN-0.4.6"


def _project_id(root: Path) -> str:
    path = root / "project.control.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            project = data.get("project") if isinstance(data, dict) else {}
            value = str((project or {}).get("id") or "").strip()
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


def _git_file_list(root: Path) -> list[Path] | None:
    git = shutil.which("git")
    if not git or not (root / ".git").exists():
        return None
    try:
        cp = subprocess.run(
            [git, "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=60, check=False,
        )
    except Exception:
        return None
    if cp.returncode != 0:
        return None
    out: list[Path] = []
    for raw in cp.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="surrogateescape")
        path = root / rel
        if path.is_file():
            out.append(path)
    return out


def _walk_file_list(root: Path) -> list[Path]:
    excluded_dirs = {
        ".git", "target", "build", "builds", "bin", "obj", "node_modules", "__pycache__",
        "artifacts", "logs", ".venv", "venv", ".idea", ".vs",
    }
    out: list[Path] = []
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        dirs[:] = [d for d in dirs if d.casefold() not in excluded_dirs]
        for name in files:
            path = current_path / name
            if path.is_file():
                out.append(path)
    return out


def governed_source_fingerprint(root: Path) -> tuple[str, int]:
    root = root.expanduser().resolve()
    files = _git_file_list(root)
    if files is None:
        files = _walk_file_list(root)
    rows: list[bytes] = []
    count = 0
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix().casefold()):
        try:
            rel = path.relative_to(root).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            size = path.stat().st_size
        except (OSError, ValueError):
            continue
        rows.append(f"{rel}\t{size}\t{digest}\n".encode("utf-8", errors="surrogateescape"))
        count += 1
    h = hashlib.sha256()
    for row in rows:
        h.update(row)
    return h.hexdigest(), count


def _git_text(root: Path, *args: str) -> str:
    git = shutil.which("git")
    if not git or not (root / ".git").exists():
        return ""
    try:
        cp = subprocess.run(
            [git, "-C", str(root), *args], cwd=str(root),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", timeout=15, check=False,
            creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0,
        )
        return cp.stdout.strip() if cp.returncode == 0 else ""
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
    current, _ = governed_source_fingerprint(root)
    return marker, current.lower() == expected, str(path), data
