#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from PCCProjectDiscovery import discovery_summary
from VaultPaths import vault_root

DRIVE_INDEX_VERSION = "VAULT-DRIVE-INDEX-0.3"
SKIP_DIRS = {
    "$recycle.bin", "system volume information", ".git", ".svn", ".hg",
    "node_modules", "target", "build", "builds", "dist", "out", ".gradle",
    ".idea", ".vs", "__pycache__", ".venv", "venv", "vendor", "packages",
}
STRONG_FILES = {
    "project.control.json", "cargo.toml", "cmakelists.txt", "pyproject.toml",
    "package.json", "settings.gradle", "settings.gradle.kts", "build.gradle", "build.gradle.kts",
    "gradlew", "gradlew.bat", "manifest.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    path = vault_root() / "catalog" / "drive_index.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(db_path())
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects(
            root TEXT PRIMARY KEY,
            scan_root TEXT NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            provider TEXT NOT NULL,
            commands INTEGER NOT NULL,
            markers_json TEXT NOT NULL,
            parent_root TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_projects_scan_root ON projects(scan_root);
        """
    )
    return db


def _looks_like_project(path: Path, names: set[str]) -> bool:
    low = {x.casefold() for x in names}
    if ".git" in low or any(name in low for name in STRONG_FILES):
        return True
    if any(x.endswith(".sln") or x.endswith(".csproj") for x in low):
        return True
    if any("controlcenter" in x and x.endswith((".ps1", ".cmd", ".py")) for x in low):
        return True
    return False


def _nearest_parent_project(path: Path, known: set[Path]) -> str:
    parent = path.parent
    while parent != parent.parent:
        if parent in known:
            return str(parent)
        parent = parent.parent
    return ""


def scan(root: Path, *, max_depth: int = 12, max_dirs: int = 250000, progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    root = root.expanduser().resolve()
    seen_dirs = 0
    candidates: list[Path] = []
    root_depth = len(root.parts)
    for base, dirs, files in os.walk(root, topdown=True, onerror=lambda _e: None):
        base_path = Path(base)
        depth = len(base_path.parts) - root_depth
        dirs[:] = [d for d in dirs if d.casefold() not in SKIP_DIRS and not d.startswith(".")]
        if depth >= max_depth:
            dirs[:] = []
        seen_dirs += 1
        names = set(files) | set(dirs)
        if _looks_like_project(base_path, names):
            candidates.append(base_path)
        if progress and seen_dirs % 500 == 0:
            progress({"directories": seen_dirs, "projects": len(candidates), "root": str(root)})
        if seen_dirs >= max_dirs:
            break

    # Shallow parents first so composite relationships are deterministic.
    candidates = sorted(set(candidates), key=lambda p: (len(p.parts), str(p).casefold()))
    known: set[Path] = set()
    records: list[dict[str, Any]] = []
    now = utc_now()
    db = _connect()
    try:
        for path in candidates:
            try:
                summary = discovery_summary(path)
            except Exception:
                summary = {"name": path.name, "kind": "project", "provider": "scan", "commands": 0, "markers": {}}
            parent = _nearest_parent_project(path, known)
            record = {
                "root": str(path),
                "scanRoot": str(root),
                "name": str(summary.get("name") or path.name),
                "kind": str(summary.get("kind") or "project"),
                "provider": str(summary.get("provider") or "scan"),
                "commands": int(summary.get("commands") or 0),
                "markers": summary.get("markers") or {},
                "parentRoot": parent,
                "lastSeenUtc": now,
            }
            db.execute(
                "INSERT OR REPLACE INTO projects(root,scan_root,name,kind,provider,commands,markers_json,parent_root,last_seen_utc) VALUES(?,?,?,?,?,?,?,?,?)",
                (record["root"], record["scanRoot"], record["name"], record["kind"], record["provider"], record["commands"], json.dumps(record["markers"], sort_keys=True), record["parentRoot"], now),
            )
            records.append(record)
            known.add(path)
        db.commit()
    finally:
        db.close()
    return {
        "schema": "vault.drive-index.scan.v1",
        "version": DRIVE_INDEX_VERSION,
        "root": str(root),
        "directories": seen_dirs,
        "projects": len(records),
        "truncated": seen_dirs >= max_dirs,
        "records": records,
        "database": str(db_path()),
    }


def list_projects(scan_root: Path | None = None) -> list[dict[str, Any]]:
    if not db_path().is_file():
        return []
    db = _connect()
    try:
        if scan_root is None:
            rows = db.execute("SELECT root,scan_root,name,kind,provider,commands,markers_json,parent_root,last_seen_utc FROM projects ORDER BY root").fetchall()
        else:
            rows = db.execute("SELECT root,scan_root,name,kind,provider,commands,markers_json,parent_root,last_seen_utc FROM projects WHERE scan_root=? ORDER BY root", (str(scan_root.expanduser().resolve()),)).fetchall()
    finally:
        db.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({
            "root": row[0], "scanRoot": row[1], "name": row[2], "kind": row[3], "provider": row[4],
            "commands": int(row[5]), "markers": json.loads(row[6] or "{}"), "parentRoot": row[7], "lastSeenUtc": row[8],
        })
    return out
