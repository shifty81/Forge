#!/usr/bin/env python3
"""Per-project read-only ForgePY compatibility reference.

The standalone ForgePY installation remains the executable/source authority.  Each
registered project receives a small Vault-side reference snapshot so adapter/patch
contracts can be audited against the exact ForgePY build in use without vendoring
ForgePY into the project repository.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ForgePYPaths import ensure_artifact_project_tree
from ForgePYVersion import VERSION, BUILD

SNAPSHOT_SCHEMA = "forgepy.project-compatibility.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def forgepy_root() -> Path:
    return Path(__file__).resolve().parents[1]


def snapshot_root(project_id: str) -> Path:
    reports = ensure_artifact_project_tree(project_id)["reports"]
    root = reports / "forgepy-compatibility" / "current"
    root.mkdir(parents=True, exist_ok=True)
    return root


def refresh(project_root: Path, project_id: str, project_name: str = "") -> dict[str, Any]:
    source = forgepy_root()
    target = snapshot_root(project_id)
    refs = (
        source / "project.control.json",
        source / "app" / "ForgePYVersion.py",
    )
    files: list[dict[str, str]] = []
    for src in refs:
        if not src.is_file():
            continue
        rel = src.relative_to(source)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        files.append({"path": rel.as_posix(), "sha256": _sha256(src)})

    project_control = project_root / "project.control.json"
    payload = {
        "schema": SNAPSHOT_SCHEMA,
        "forgePyVersion": VERSION,
        "forgePyBuild": BUILD,
        "forgePyRoot": str(source),
        "projectId": project_id,
        "projectName": project_name or project_root.name,
        "projectRoot": str(project_root.resolve()),
        "projectControlSha256": _sha256(project_control),
        "capturedUtc": datetime.now(timezone.utc).isoformat(),
        "referenceFiles": files,
        "mode": "read-only-vault-reference",
    }
    manifest = target / "compatibility.json"
    manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**payload, "path": str(manifest)}


def status(project_id: str) -> dict[str, Any]:
    manifest = snapshot_root(project_id) / "compatibility.json"
    if not manifest.is_file():
        return {"state": "AUDIT REQUIRED", "forgePyVersion": VERSION, "forgePyBuild": BUILD}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"state": "AUDIT REQUIRED", "forgePyVersion": VERSION, "forgePyBuild": BUILD}
    current = str(data.get("forgePyBuild") or "") == BUILD
    return {**data, "state": "CURRENT" if current else "UPDATE AVAILABLE"}
