#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from VaultPaths import ensure_artifact_project_tree, project_artifact_root

ARTIFACT_VERSION = "VAULT-ARTIFACTS-0.4"

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("debug-bundles", re.compile(r"debug[_ -]?bundle|diagnostic|support[_ -]?bundle", re.I)),
    ("source-rollups", re.compile(r"source[_ -]?(rollup|bundle)|complete[_ -]?source|sourceonly", re.I)),
    ("baselines", re.compile(r"baseline|authority|checkpoint", re.I)),
    ("backups", re.compile(r"backup|recovery|snapshot", re.I)),
    ("releases", re.compile(r"release|installer|setup|portable", re.I)),
    ("reports", re.compile(r"report|audit|attestation|manifest", re.I)),
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_project_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-") or "unassigned"


def classify_artifact(path: Path) -> str:
    name = path.name
    if re.search(r"patch", name, re.I):
        return "patches"
    for category, pattern in _PATTERNS:
        if pattern.search(name):
            return category
    ext = path.suffix.casefold()
    if ext in {".blend", ".fbx", ".glb", ".gltf", ".obj", ".png", ".aseprite", ".wav", ".ogg"}:
        return "asset-intake"
    if ext in {".log"}:
        return "logs"
    return "review"



def identify_project(path: Path, *, root_hint: Path | None = None) -> str | None:
    """Resolve an artifact to a registered project without guessing broadly.

    A file found in a registered project root belongs to that project.  Files from
    global intake areas such as Downloads must carry a recognizable registered
    project name/id in the filename before Vault moves them automatically.
    """
    try:
        from PCCSurfaceCommon import ProjectRegistry
        entries = ProjectRegistry().entries()
    except Exception:
        entries = []

    if root_hint is not None:
        try:
            resolved_hint = root_hint.expanduser().resolve()
        except Exception:
            resolved_hint = root_hint
        for entry in entries:
            try:
                if entry.root.resolve() == resolved_hint:
                    return entry.project_id or entry.name
            except Exception:
                pass

    token = re.sub(r"[^a-z0-9]+", "", path.stem.casefold())
    best: tuple[int, str] | None = None
    for entry in entries:
        aliases = {entry.project_id, entry.name, entry.root.name}
        for alias in aliases:
            norm = re.sub(r"[^a-z0-9]+", "", str(alias).casefold())
            if len(norm) < 4 or norm not in token:
                continue
            candidate = (len(norm), entry.project_id or entry.name)
            if best is None or candidate[0] > best[0]:
                best = candidate
    return best[1] if best else None


def auto_archive_candidate(path: Path) -> bool:
    """Return True only for artifact classes safe enough for automatic intake."""
    category = classify_artifact(path)
    if category != "review":
        return True
    # Generic documents/binaries remain in Downloads unless a stronger classifier exists.
    return False

def archive_file(source: Path, project_id: str, *, category: str | None = None, move: bool = True, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    pid = safe_project_id(project_id)
    tree = ensure_artifact_project_tree(pid)
    cat = category or classify_artifact(source)
    target_parent = tree.get(cat) or tree["review"]
    stamp = datetime.now().strftime("%Y/%m/%Y%m%d-%H%M%S")
    folder = target_parent / stamp
    folder.mkdir(parents=True, exist_ok=True)
    digest = _sha256(source)
    target = folder / source.name
    if target.exists() and _sha256(target) != digest:
        target = folder / f"{source.stem}-{digest[:10]}{source.suffix}"
    if not target.exists():
        temp = target.with_suffix(target.suffix + ".copying")
        shutil.copy2(source, temp)
        if _sha256(temp) != digest:
            temp.unlink(missing_ok=True)
            raise RuntimeError("Artifact Central copy hash mismatch")
        os.replace(temp, target)
    receipt = {
        "schema": "vault.artifact.receipt.v1",
        "version": ARTIFACT_VERSION,
        "projectId": pid,
        "category": cat,
        "originalPath": str(source),
        "artifactPath": str(target),
        "sha256": digest,
        "bytes": source.stat().st_size,
        "receivedUtc": _utc(),
        "metadata": metadata or {},
    }
    (folder / "artifact.receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if move and source != target:
        source.unlink(missing_ok=True)
    return receipt


def summary(project_id: str) -> dict[str, Any]:
    root = project_artifact_root(safe_project_id(project_id))
    ensure_artifact_project_tree(safe_project_id(project_id))
    counts: dict[str, int] = {}
    total = 0
    for child in root.iterdir() if root.is_dir() else []:
        if not child.is_dir():
            continue
        count = sum(1 for p in child.rglob("*") if p.is_file() and p.name != "artifact.receipt.json")
        counts[child.name] = count
        total += count
    return {"root": str(root), "files": total, "categories": counts}


__all__ = ["archive_file", "auto_archive_candidate", "classify_artifact", "identify_project", "safe_project_id", "summary"]
