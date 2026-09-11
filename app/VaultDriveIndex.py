#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from PCCProjectDiscovery import discovery_summary
from PCCVaultCatalog import classify_path
from VaultPaths import vault_root

DRIVE_INDEX_VERSION = "FORGEPY-DRIVE-CATALOG-0.4"
SYSTEM_SKIP_DIRS = {"$recycle.bin", "system volume information"}
SOFT_SKIP_DIRS = {".git", ".svn", ".hg"}
STRONG_AUTHORITY_FILES = {"project.control.json"}
WORKSPACE_FILES = {
    "pyproject.toml", "package.json", "settings.gradle", "settings.gradle.kts",
    "build.gradle", "build.gradle.kts", "cmakelists.txt",
}
PATCH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,95}__\d{8}__[A-Za-z0-9][A-Za-z0-9._+-]{0,63}\.(?:patch|zip)$", re.I)
VERSION_HINT_RE = re.compile(r"(?:[-_.](?:v|ver|version)?\d+(?:[._-]\d+){0,3}|[-_.]\d{8}(?:[-_.]\d{4,6})?)$", re.I)
COMMON_COPY_SUFFIX_RE = re.compile(r"(?:[-_.](?:main|master|copy|old|older|backup|bak|archive|archived|legacy|source|src))+$", re.I)
HASH_LIMIT = 32 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    path = vault_root() / "catalog" / "drive_index.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_column(db: sqlite3.Connection, table: str, name: str, decl: str) -> None:
    if name not in _table_columns(db, table):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def _connect() -> sqlite3.Connection:
    """Open the derived drive catalog and forward-migrate older ForgePY schemas.

    Important: schema migration must occur before indexes referencing newly-added
    columns are created. F60R22 created idx_projects_family before adding
    projects.family_hint, which made upgraded F60R17/F60R12 catalogs fail at
    application startup with "no such column: family_hint".
    """
    db = sqlite3.connect(db_path())
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")

    # Create tables first, but deliberately defer indexes until after additive
    # forward migration. The drive catalog is derived data; this migration never
    # alters project source or Vault payload files.
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS scan_runs(
            scan_id TEXT PRIMARY KEY,
            scan_root TEXT NOT NULL,
            started_utc TEXT NOT NULL,
            completed_utc TEXT NOT NULL,
            directories INTEGER NOT NULL,
            files INTEGER NOT NULL,
            projects INTEGER NOT NULL,
            components INTEGER NOT NULL,
            unknown INTEGER NOT NULL,
            truncated INTEGER NOT NULL,
            summary_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS projects(
            root TEXT PRIMARY KEY,
            scan_root TEXT NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            provider TEXT NOT NULL,
            commands INTEGER NOT NULL,
            markers_json TEXT NOT NULL,
            parent_root TEXT NOT NULL,
            family_hint TEXT NOT NULL DEFAULT '',
            strength INTEGER NOT NULL DEFAULT 0,
            last_seen_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS entries(
            path TEXT PRIMARY KEY,
            scan_root TEXT NOT NULL,
            parent_path TEXT NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            classification TEXT NOT NULL,
            bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            extension TEXT NOT NULL,
            owner_project_root TEXT NOT NULL,
            family_hint TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            note TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL
        );
        """
    )

    # F60R17 and earlier had only the narrower projects table. Keep those rows
    # and add the new lineage columns before any dependent indexes are created.
    _ensure_column(db, "projects", "family_hint", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(db, "projects", "strength", "INTEGER NOT NULL DEFAULT 0")

    # Defensive additive migration for any intermediate catalog build that may
    # already contain an entries table with fewer columns.
    entry_columns = (
        ("scan_root", "TEXT NOT NULL DEFAULT ''"),
        ("parent_path", "TEXT NOT NULL DEFAULT ''"),
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("kind", "TEXT NOT NULL DEFAULT 'file'"),
        ("classification", "TEXT NOT NULL DEFAULT 'UNKNOWN'"),
        ("bytes", "INTEGER NOT NULL DEFAULT 0"),
        ("mtime_ns", "INTEGER NOT NULL DEFAULT 0"),
        ("extension", "TEXT NOT NULL DEFAULT ''"),
        ("owner_project_root", "TEXT NOT NULL DEFAULT ''"),
        ("family_hint", "TEXT NOT NULL DEFAULT ''"),
        ("sha256", "TEXT NOT NULL DEFAULT ''"),
        ("note", "TEXT NOT NULL DEFAULT ''"),
        ("last_seen_utc", "TEXT NOT NULL DEFAULT ''"),
    )
    for name, decl in entry_columns:
        _ensure_column(db, "entries", name, decl)

    # Only now is it safe to create indexes that reference migrated columns.
    db.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_projects_scan_root ON projects(scan_root);
        CREATE INDEX IF NOT EXISTS idx_projects_parent ON projects(parent_root);
        CREATE INDEX IF NOT EXISTS idx_projects_family ON projects(family_hint);
        CREATE INDEX IF NOT EXISTS idx_entries_scan_root ON entries(scan_root);
        CREATE INDEX IF NOT EXISTS idx_entries_class ON entries(classification);
        CREATE INDEX IF NOT EXISTS idx_entries_owner ON entries(owner_project_root);
        CREATE INDEX IF NOT EXISTS idx_entries_family ON entries(family_hint);
        CREATE INDEX IF NOT EXISTS idx_entries_hash ON entries(sha256);
        CREATE INDEX IF NOT EXISTS idx_entries_name ON entries(name);
        """
    )
    db.commit()
    return db


def _family_hint(path: Path) -> str:
    name = path.name.casefold().strip()
    name = VERSION_HINT_RE.sub("", name)
    name = COMMON_COPY_SUFFIX_RE.sub("", name)
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name or path.name.casefold()


def _project_strength(path: Path, files: set[str], dirs: set[str]) -> int:
    low_files = {x.casefold() for x in files}
    low_dirs = {x.casefold() for x in dirs}
    if "project.control.json" in low_files:
        return 100
    if ".git" in low_dirs:
        return 98
    if any(x.endswith(".sln") for x in low_files):
        return 94
    cargo = path / "Cargo.toml"
    if "cargo.toml" in low_files:
        try:
            raw = cargo.read_text(encoding="utf-8-sig", errors="replace")[:256 * 1024]
            if "[workspace]" in raw:
                return 92
        except Exception:
            pass
        return 62
    if "pyproject.toml" in low_files:
        return 86
    if "settings.gradle" in low_files or "settings.gradle.kts" in low_files:
        return 86
    if "package.json" in low_files:
        return 82
    if "cmakelists.txt" in low_files:
        return 80
    if any(x.endswith(".csproj") for x in low_files):
        return 64
    if any("controlcenter" in x and x.endswith((".ps1", ".cmd", ".py")) for x in low_files):
        return 90
    return 0


def _nearest_ancestor(path: Path, roots: set[Path]) -> Path | None:
    parent = path.parent
    while parent != parent.parent:
        if parent in roots:
            return parent
        parent = parent.parent
    return None


def _classify_drive_entry(scan_root: Path, path: Path, *, is_dir: bool, owner: Path | None) -> str:
    name = path.name.casefold()
    ext = path.suffix.casefold()
    if not is_dir and PATCH_NAME_RE.fullmatch(path.name):
        return "PATCH_TRANSPORT"
    if not is_dir and ext == ".patch":
        return "PATCH_TRANSPORT"
    base = owner if owner is not None else scan_root
    category = classify_path(base, path, is_dir=is_dir)
    if category == "UNKNOWN" and not is_dir:
        if ext in {".exe", ".dll", ".pdb", ".msi", ".msix"}:
            return "BINARY"
        if ext in {".iso", ".img", ".vhd", ".vhdx"}:
            return "DISK_IMAGE"
    if category == "COMPONENT" and owner is None:
        return "DIRECTORY"
    if category == "SOURCE" and owner is not None:
        return "PROJECT_SOURCE"
    if category == "ASSET" and owner is not None:
        return "PROJECT_ASSET"
    if category == "CONTROL" and owner is not None:
        return "PROJECT_CONTROL"
    if category == "CONFIG" and owner is not None:
        return "PROJECT_CONFIG"
    if category == "DOCUMENTATION" and owner is not None:
        return "PROJECT_DOCUMENTATION"
    return category


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def scan(
    root: Path,
    *,
    max_depth: int = 24,
    max_dirs: int = 500000,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Catalog the whole configured Vault drive/root, not only project markers.

    The scan is non-destructive. Every visible directory/file is classified and linked
    to the nearest authoritative project when possible. Potential project copies are
    grouped by a conservative family hint for later lineage review; no source is moved.
    """
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    started = utc_now()
    scan_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root_depth = len(root.parts)
    seen_dirs = 0
    file_count = 0
    raw_entries: list[tuple[Path, bool, int, int]] = []
    candidate_info: dict[Path, tuple[int, set[str], set[str]]] = {}

    for base, dirs, files in os.walk(root, topdown=True, onerror=lambda _e: None):
        base_path = Path(base)
        depth = len(base_path.parts) - root_depth
        original_dirs = list(dirs)
        dirs[:] = [d for d in dirs if d.casefold() not in SYSTEM_SKIP_DIRS]
        if depth >= max_depth:
            dirs[:] = []
        seen_dirs += 1
        try:
            st = base_path.stat()
            raw_entries.append((base_path, True, 0, int(st.st_mtime_ns)))
        except OSError:
            pass

        strength = _project_strength(base_path, set(files), set(original_dirs))
        if strength:
            candidate_info[base_path] = (strength, set(files), set(original_dirs))

        for filename in files:
            path = base_path / filename
            try:
                st = path.stat()
                if not path.is_file():
                    continue
                raw_entries.append((path, False, int(st.st_size), int(st.st_mtime_ns)))
                file_count += 1
            except OSError:
                continue
        if progress and seen_dirs % 300 == 0:
            progress({"directories": seen_dirs, "files": file_count, "candidates": len(candidate_info), "root": str(root), "phase": "inventory"})
        if seen_dirs >= max_dirs:
            break

    # Classify project authorities versus nested buildable components. A nested root
    # with its own project.control/.git/workspace remains independently authoritative.
    ordered = sorted(candidate_info, key=lambda p: (len(p.parts), str(p).casefold()))
    project_roots: set[Path] = set()
    component_roots: set[Path] = set()
    parent_map: dict[Path, Path | None] = {}
    for path in ordered:
        strength = candidate_info[path][0]
        parent = _nearest_ancestor(path, project_roots | component_roots)
        independently_authoritative = strength >= 92
        if parent is None or independently_authoritative:
            project_roots.add(path)
        else:
            component_roots.add(path)
        parent_map[path] = parent

    ownership_roots = project_roots | component_roots
    class_counts: Counter[str] = Counter()
    unknown = 0
    now = utc_now()
    db = _connect()
    try:
        db.execute("DELETE FROM projects WHERE scan_root=?", (str(root),))
        db.execute("DELETE FROM entries WHERE scan_root=?", (str(root),))

        project_records: list[dict[str, Any]] = []
        for path in ordered:
            strength = candidate_info[path][0]
            kind = "project" if path in project_roots else "component"
            try:
                summary = discovery_summary(path)
            except Exception:
                summary = {"name": path.name, "kind": kind, "provider": "drive-scan", "commands": 0, "markers": {}}
            parent = parent_map.get(path)
            record = {
                "root": str(path), "scanRoot": str(root), "name": str(summary.get("name") or path.name),
                "kind": kind, "provider": str(summary.get("provider") or "drive-scan"),
                "commands": int(summary.get("commands") or 0), "markers": summary.get("markers") or {},
                "parentRoot": str(parent) if parent else "", "familyHint": _family_hint(path),
                "strength": strength, "lastSeenUtc": now,
            }
            db.execute(
                "INSERT OR REPLACE INTO projects(root,scan_root,name,kind,provider,commands,markers_json,parent_root,family_hint,strength,last_seen_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (record["root"], record["scanRoot"], record["name"], record["kind"], record["provider"], record["commands"], json.dumps(record["markers"], sort_keys=True), record["parentRoot"], record["familyHint"], strength, now),
            )
            project_records.append(record)

        owner_cache: dict[Path, Path | None] = {}
        for index, (path, is_dir, size, mtime_ns) in enumerate(raw_entries, 1):
            if path in ownership_roots:
                owner = path
            else:
                parent = path.parent if not is_dir else path
                owner = owner_cache.get(parent)
                if parent not in owner_cache:
                    owner = _nearest_ancestor(path, ownership_roots)
                    owner_cache[parent] = owner
            classification = "PROJECT_ROOT" if path in project_roots else ("PROJECT_COMPONENT" if path in component_roots else _classify_drive_entry(root, path, is_dir=is_dir, owner=owner))
            class_counts[classification] += 1
            if classification in {"UNKNOWN", "DIRECTORY"} and not is_dir:
                unknown += 1
            digest = ""
            note = ""
            if not is_dir and size <= HASH_LIMIT and classification in {"PATCH_TRANSPORT", "ARCHIVE", "PROJECT_CONTROL", "CONTROL"}:
                try:
                    digest = _sha256(path)
                except OSError as exc:
                    note = f"hash failed: {exc}"
            family = _family_hint(owner) if owner else _family_hint(path.parent)
            db.execute(
                "INSERT OR REPLACE INTO entries(path,scan_root,parent_path,name,kind,classification,bytes,mtime_ns,extension,owner_project_root,family_hint,sha256,note,last_seen_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(path), str(root), str(path.parent), path.name, "directory" if is_dir else "file", classification, size, mtime_ns, path.suffix.casefold(), str(owner) if owner else "", family, digest, note, now),
            )
            if index % 2000 == 0:
                db.commit()
                if progress:
                    progress({"directories": seen_dirs, "files": file_count, "entries": index, "projects": len(project_roots), "components": len(component_roots), "root": str(root), "phase": "classify"})

        summary = {
            "schema": "forgepy.drive-catalog.scan.v2", "version": DRIVE_INDEX_VERSION,
            "scanId": scan_id, "root": str(root), "directories": seen_dirs, "files": file_count,
            "entries": len(raw_entries), "projects": len(project_roots), "components": len(component_roots),
            "unknown": unknown, "classCounts": dict(sorted(class_counts.items())),
            "truncated": seen_dirs >= max_dirs, "startedUtc": started, "completedUtc": now,
        }
        db.execute(
            "INSERT OR REPLACE INTO scan_runs(scan_id,scan_root,started_utc,completed_utc,directories,files,projects,components,unknown,truncated,summary_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (scan_id, str(root), started, now, seen_dirs, file_count, len(project_roots), len(component_roots), unknown, int(seen_dirs >= max_dirs), json.dumps(summary, sort_keys=True)),
        )
        db.commit()
    finally:
        db.close()

    if progress:
        progress({**summary, "done": True, "phase": "done"})
    return {**summary, "records": project_records, "database": str(db_path())}


def list_projects(scan_root: Path | None = None, *, include_components: bool = True) -> list[dict[str, Any]]:
    if not db_path().is_file():
        return []
    db = _connect()
    try:
        sql = "SELECT root,scan_root,name,kind,provider,commands,markers_json,parent_root,family_hint,strength,last_seen_utc FROM projects"
        where: list[str] = []
        args: list[Any] = []
        if scan_root is not None:
            where.append("scan_root=?"); args.append(str(scan_root.expanduser().resolve()))
        if not include_components:
            where.append("kind='project'")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY kind DESC, root"
        rows = db.execute(sql, args).fetchall()
    finally:
        db.close()
    out = []
    for row in rows:
        out.append({
            "root": row[0], "scanRoot": row[1], "name": row[2], "kind": row[3], "provider": row[4],
            "commands": int(row[5]), "markers": json.loads(row[6] or "{}"), "parentRoot": row[7],
            "familyHint": row[8], "strength": int(row[9] or 0), "lastSeenUtc": row[10],
        })
    return out


def list_entries(scan_root: Path | None = None, *, classification: str | None = None, owner_project_root: Path | None = None, limit: int = 5000, offset: int = 0) -> list[dict[str, Any]]:
    if not db_path().is_file():
        return []
    db = _connect()
    try:
        sql = "SELECT path,scan_root,parent_path,name,kind,classification,bytes,mtime_ns,extension,owner_project_root,family_hint,sha256,note,last_seen_utc FROM entries"
        where: list[str] = []
        args: list[Any] = []
        if scan_root is not None:
            where.append("scan_root=?"); args.append(str(scan_root.expanduser().resolve()))
        if classification:
            where.append("classification=?"); args.append(str(classification))
        if owner_project_root is not None:
            where.append("owner_project_root=?"); args.append(str(owner_project_root.expanduser().resolve()))
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY path LIMIT ? OFFSET ?"; args.extend((max(1, int(limit)), max(0, int(offset))))
        rows = db.execute(sql, args).fetchall()
    finally:
        db.close()
    keys = ["path","scanRoot","parentPath","name","kind","classification","bytes","mtimeNs","extension","ownerProjectRoot","familyHint","sha256","note","lastSeenUtc"]
    return [dict(zip(keys, row)) for row in rows]


def search_entries(query: str, *, scan_root: Path | None = None, limit: int = 1000, offset: int = 0) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return list_entries(scan_root, limit=limit, offset=offset)
    if not db_path().is_file():
        return []
    db = _connect()
    try:
        sql = "SELECT path,scan_root,parent_path,name,kind,classification,bytes,mtime_ns,extension,owner_project_root,family_hint,sha256,note,last_seen_utc FROM entries WHERE (lower(name) LIKE ? OR lower(path) LIKE ? OR lower(classification) LIKE ? OR lower(family_hint) LIKE ?)"
        needle = f"%{q.casefold()}%"
        args: list[Any] = [needle, needle, needle, needle]
        if scan_root is not None:
            sql += " AND scan_root=?"; args.append(str(scan_root.expanduser().resolve()))
        sql += " ORDER BY path LIMIT ? OFFSET ?"; args.extend((max(1, int(limit)), max(0, int(offset))))
        rows = db.execute(sql, args).fetchall()
    finally:
        db.close()
    keys = ["path","scanRoot","parentPath","name","kind","classification","bytes","mtimeNs","extension","ownerProjectRoot","familyHint","sha256","note","lastSeenUtc"]
    return [dict(zip(keys, row)) for row in rows]


def entry_counts(scan_root: Path | None = None) -> dict[str, int]:
    if not db_path().is_file():
        return {}
    db = _connect()
    try:
        args: list[Any] = []
        where = ""
        if scan_root is not None:
            where = " WHERE scan_root=?"; args.append(str(scan_root.expanduser().resolve()))
        rows = db.execute("SELECT classification, COUNT(*) FROM entries" + where + " GROUP BY classification", args).fetchall()
    finally:
        db.close()
    return {str(name): int(count) for name, count in rows}


def latest_summary(scan_root: Path | None = None) -> dict[str, Any]:
    if not db_path().is_file():
        return {}
    db = _connect()
    try:
        if scan_root is None:
            row = db.execute("SELECT summary_json FROM scan_runs ORDER BY completed_utc DESC LIMIT 1").fetchone()
        else:
            row = db.execute("SELECT summary_json FROM scan_runs WHERE scan_root=? ORDER BY completed_utc DESC LIMIT 1", (str(scan_root.expanduser().resolve()),)).fetchone()
    finally:
        db.close()
    if not row:
        return {}
    try:
        return json.loads(row[0])
    except Exception:
        return {}


def lineage_groups(scan_root: Path | None = None, *, limit: int = 500) -> list[dict[str, Any]]:
    """Conservative project-family groupings for review; no automatic moves."""
    projects = list_projects(scan_root, include_components=False)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in projects:
        grouped.setdefault(str(row.get("familyHint") or "unknown"), []).append(row)
    out = []
    for family, rows in grouped.items():
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda x: str(x.get("lastSeenUtc") or ""), reverse=True)
        out.append({"familyHint": family, "count": len(rows), "primaryCandidate": rows[0], "members": rows})
    out.sort(key=lambda x: (-int(x["count"]), str(x["familyHint"])))
    return out[: max(1, int(limit))]
