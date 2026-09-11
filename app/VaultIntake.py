#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence

from VaultSettings import load_settings
from VaultBuildIdentity import verify_manifest_preconditions

from VaultPaths import downloads_roots, intake_roots, vault_root, ensure_artifact_project_tree
from VaultArtifacts import archive_file as archive_artifact_file, auto_archive_candidate, classify_artifact, identify_project

VAULT_INTAKE_VERSION = "FORGEPY-INTAKE-0.4.22"
TEMP_SUFFIXES = {".crdownload", ".part", ".download", ".tmp"}
PATCH_SUFFIXES = {".zip", ".patch"}
INCOMING_PATCH_NAME = "incoming.patch"
NON_PATCH_RE = re.compile(r"(?:debugbundle|debug[-_ ]?bundle|handoff|source[-_ ]?(?:rollup|bundle)|rollup|backup|support[-_ ]?bundle|archive)", re.I)
PATCH_NAME_RE = re.compile(r"(?:root[-_ ]?patch|rootpatch|incremental[-_ ]?patch|patch[-_ ]?update|[_-]patch[_-]|^patch[_-])", re.I)
PATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
CANONICAL_PATCH_FILE_RE = re.compile(r"^(?P<project>[A-Za-z0-9][A-Za-z0-9._-]{1,95})__(?P<date>\d{8})__(?P<version>[A-Za-z0-9][A-Za-z0-9._+-]{0,63})\.(?P<ext>patch|zip)$", re.I)
MAX_FILES = 5000
MAX_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
MAX_SINGLE_FILE = 512 * 1024 * 1024
MAX_PATH_CHARS = 260
DEFAULT_STABLE_SECONDS = 2.0


class IntakeError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_canonical_patch_filename(path: Path | str) -> dict[str, str]:
    """Parse the ForgePY Downloads naming contract.

    Canonical browser/download transport names are:
      ProjectName__YYYYMMDD__Version.patch
    The manifest remains authoritative; filename metadata is routing assistance.
    """
    name = Path(path).name if not isinstance(path, Path) else path.name
    match = CANONICAL_PATCH_FILE_RE.fullmatch(name)
    if not match:
        return {}
    out = {k: str(v) for k, v in match.groupdict().items()}
    try:
        datetime.strptime(out["date"], "%Y%m%d")
    except ValueError:
        return {}
    return out


def canonical_patch_filename(project: str, version: str, *, when: datetime | None = None, suffix: str = ".patch") -> str:
    stamp = (when or datetime.now()).strftime("%Y%m%d")
    safe_project = re.sub(r"[^A-Za-z0-9._-]+", "-", str(project or "Project")).strip("-._") or "Project"
    safe_version = re.sub(r"[^A-Za-z0-9._+-]+", "-", str(version or "update")).strip("-._") or "update"
    ext = ".zip" if str(suffix).casefold() == ".zip" else ".patch"
    return f"{safe_project}__{stamp}__{safe_version}{ext}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _promote_verified(source: Path, destination: Path, expected_sha256: str, *, remove_source: bool = True) -> Path:
    """Promote a verified file without relying on cross-volume rename semantics.

    Windows os.replace cannot move C: -> D:.  Always stage a temporary copy beside the
    destination, verify it, atomically rename *within* that volume, then optionally delete
    the source quarantine file.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + f".forge-copying-{uuid.uuid4().hex[:8]}")
    try:
        shutil.copy2(source, temp)
        if sha256_file(temp) != expected_sha256:
            raise IntakeError(f"destination-volume copy hash mismatch: {destination.name}")
        os.replace(temp, destination)
        if sha256_file(destination) != expected_sha256:
            raise IntakeError(f"destination promotion hash mismatch: {destination.name}")
        if remove_source:
            source.unlink(missing_ok=True)
        return destination
    finally:
        temp.unlink(missing_ok=True)


def _db_path() -> Path:
    path = vault_root() / "catalog" / "forge_intake.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(_db_path())
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS observations(
            source_path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            stable_count INTEGER NOT NULL,
            first_seen_utc TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS intake_items(
            intake_id TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            original_path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            bytes INTEGER NOT NULL,
            classification TEXT NOT NULL,
            state TEXT NOT NULL,
            target_project TEXT NOT NULL,
            patch_id TEXT NOT NULL,
            received_utc TEXT NOT NULL,
            vault_path TEXT NOT NULL,
            manifest_json TEXT NOT NULL,
            error TEXT NOT NULL,
            approved_utc TEXT NOT NULL DEFAULT '',
            approved_root TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_intake_state ON intake_items(state);
        CREATE INDEX IF NOT EXISTS idx_intake_project ON intake_items(target_project, state);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_intake_hash_state ON intake_items(sha256, state);
        CREATE TABLE IF NOT EXISTS rejected_observations(
            source_path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            error TEXT NOT NULL,
            first_seen_utc TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL
        );
        """
    )
    # Older Forge/Vault catalogs predate explicit approval evidence.  Migrate them
    # in place without invalidating existing intake history.
    columns = {str(row[1]) for row in db.execute("PRAGMA table_info(intake_items)").fetchall()}
    if "approved_utc" not in columns:
        db.execute("ALTER TABLE intake_items ADD COLUMN approved_utc TEXT NOT NULL DEFAULT ''")
    if "approved_root" not in columns:
        db.execute("ALTER TABLE intake_items ADD COLUMN approved_root TEXT NOT NULL DEFAULT ''")
    db.commit()
    return db


def _safe_zip_entries(zf: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    total = 0
    for info in zf.infolist():
        raw = info.filename.replace("\\", "/")
        if not raw or raw.endswith("/"):
            continue
        p = PurePosixPath(raw)
        if p.is_absolute() or re.match(r"^[A-Za-z]:", raw) or any(part in {"", ".", ".."} for part in p.parts):
            raise IntakeError(f"unsafe ZIP path: {raw}")
        normalized = "/".join(p.parts)
        if len(normalized) > MAX_PATH_CHARS:
            raise IntakeError(f"ZIP path too long: {normalized}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if mode and (stat.S_ISLNK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode)):
            raise IntakeError(f"non-regular ZIP entry: {normalized}")
        if info.file_size > MAX_SINGLE_FILE:
            raise IntakeError(f"ZIP entry exceeds safety budget: {normalized}")
        total += info.file_size
        if total > MAX_UNCOMPRESSED:
            raise IntakeError("ZIP exceeds uncompressed safety budget")
        names.append(normalized)
    if len(names) > MAX_FILES + 5:
        raise IntakeError(f"ZIP exceeds file-count safety budget ({MAX_FILES})")
    folded = [name.casefold() for name in names]
    if len(folded) != len(set(folded)):
        raise IntakeError("ZIP contains duplicate paths (case-insensitive)")
    return names


def inspect_patch(path: Path) -> dict[str, Any]:
    if path.suffix.casefold() not in PATCH_SUFFIXES:
        raise IntakeError("not a ZIP-compatible patch transport")
    zip_min_utc = ""
    zip_max_utc = ""
    with zipfile.ZipFile(path, "r") as zf:
        names = _safe_zip_entries(zf)
        zip_dates = []
        for info in zf.infolist():
            if info.filename.endswith("/"):
                continue
            try:
                # ZIP timestamps have no timezone. Treat them as local packaging-clock evidence only.
                dt = datetime(*info.date_time, tzinfo=timezone.utc)
                zip_dates.append(dt)
            except Exception:
                pass
        if zip_dates:
            zip_min_utc = min(zip_dates).isoformat()
            zip_max_utc = max(zip_dates).isoformat()
        matches = [name for name in names if name.casefold() == "patch_manifest.json"]
        if len(matches) != 1:
            raise IntakeError("patch transport requires exactly one top-level PATCH_MANIFEST.json")
        manifest_name = matches[0]
        if PurePosixPath(manifest_name).parent != PurePosixPath("."):
            raise IntakeError("PATCH_MANIFEST.json must be top-level")
        try:
            manifest = json.loads(zf.read(manifest_name).decode("utf-8-sig"))
        except Exception as exc:
            raise IntakeError(f"invalid PATCH_MANIFEST.json: {exc}") from exc
        if not isinstance(manifest, dict):
            raise IntakeError("PATCH_MANIFEST.json must be an object")

    patch_id = str(manifest.get("patchId") or manifest.get("patch_id") or "").strip()
    if not patch_id or len(patch_id) > 128:
        raise IntakeError("patchId must be present and no longer than 128 characters")
    legacy_patch_id = not bool(PATCH_ID_RE.fullmatch(patch_id))
    project = str(
        manifest.get("project")
        or manifest.get("projectId")
        or manifest.get("project_id")
        or manifest.get("targetProject")
        or manifest.get("target_project")
        or "unassigned"
    ).strip()
    target = manifest.get("target")
    if project == "unassigned" and isinstance(target, dict):
        project = str(target.get("project") or target.get("projectId") or target.get("id") or "unassigned").strip()
    filename_meta = parse_canonical_patch_filename(path)
    if project == "unassigned" and filename_meta.get("project"):
        project = str(filename_meta["project"]).strip()
    schema = str(manifest.get("schema") or "").strip()
    modern = schema.casefold().startswith("vault.patch.v2") or schema.casefold().startswith("forge.patch.v1")
    security = load_settings().get("security", {}) or {}
    strict_modern = bool(security.get("strictModernPatches", True))
    if modern and strict_modern and not PATCH_ID_RE.fullmatch(patch_id):
        raise IntakeError("modern Vault patchId must be a canonical 3-128 character identifier")
    created_raw = str(manifest.get("createdUtc") or manifest.get("createdAt") or manifest.get("packageDate") or manifest.get("timestampUtc") or "").strip()
    package_created_utc = ""
    date_status = "LEGACY-MISSING" if not created_raw else "PASS"
    if created_raw:
        try:
            parsed = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            parsed = parsed.astimezone(timezone.utc)
            package_created_utc = parsed.isoformat()
            settings = load_settings().get("intake", {}) or {}
            future_minutes = float(settings.get("futureClockToleranceMinutes", 10) or 10)
            if parsed > datetime.now(timezone.utc) + timedelta(minutes=future_minutes):
                raise IntakeError(f"package date is implausibly in the future: {created_raw}")
            # Cross-check declared package time against ZIP member clock evidence. ZIP stores a
            # timezone-less DOS timestamp, so this is deliberately a broad tamper/staleness check.
            if zip_max_utc:
                zip_max = datetime.fromisoformat(zip_max_utc)
                tolerance = float(settings.get("packageClockToleranceHours", 48) or 48)
                if abs((zip_max - parsed).total_seconds()) > tolerance * 3600:
                    date_status = "WARN-ZIP-CLOCK"
        except IntakeError:
            raise
        except Exception as exc:
            raise IntakeError(f"invalid package date: {created_raw}: {exc}") from exc
    elif modern and strict_modern:
        raise IntakeError("modern Vault patch requires createdUtc/package date evidence")
    elif bool((load_settings().get("intake", {}) or {}).get("requirePackageDate", False)):
        raise IntakeError("package date is required by Vault intake policy")

    declared_binding: dict[str, Any] = {}
    for key in ("requires", "preconditions", "targetBuild"):
        value = manifest.get(key)
        if isinstance(value, dict):
            declared_binding.update(value)
    binding_keys = {"gitCommit", "gitHead", "commit", "sourceCommit", "projectVersion", "version", "targetVersion", "projectBuild", "build", "buildId", "baseline", "greenId", "gateId", "green"}
    bound_fields = sorted(str(k) for k, v in declared_binding.items() if k in binding_keys and v not in (None, ""))
    build_bound = bool(bound_fields)
    if modern and strict_modern and bool(security.get("requireModernBuildBinding", True)) and not build_bound:
        raise IntakeError("modern Vault patch requires target build/source identity preconditions")
    verification_class = "MODERN-BOUND" if modern and build_bound else ("MODERN-UNBOUND" if modern else ("LEGACY-BOUND" if build_bound else "LEGACY-UNBOUND"))
    return {
        "patchId": patch_id,
        "legacyPatchId": legacy_patch_id,
        "packageCreatedUtc": package_created_utc,
        "dateStatus": date_status,
        "zipMinUtc": zip_min_utc,
        "zipMaxUtc": zip_max_utc,
        "project": project or "unassigned",
        "schema": schema,
        "modern": modern,
        "buildBound": build_bound,
        "boundFields": bound_fields,
        "verificationClass": verification_class,
        "title": str(manifest.get("title") or patch_id),
        "filenameMeta": filename_meta,
        "manifest": manifest,
    }


def looks_like_patch(path: Path) -> bool:
    if not path.is_file() or path.suffix.casefold() not in PATCH_SUFFIXES:
        return False
    if NON_PATCH_RE.search(path.name):
        return False
    try:
        with zipfile.ZipFile(path, "r") as zf:
            return any(name.replace("\\", "/").casefold() == "patch_manifest.json" for name in zf.namelist())
    except Exception:
        return False


def _observe(path: Path) -> int:
    stat_result = path.stat()
    key = os.path.normcase(str(path.resolve()))
    now = utc_now()
    db = _connect()
    try:
        row = db.execute("SELECT size,mtime_ns,stable_count,first_seen_utc FROM observations WHERE source_path=?", (key,)).fetchone()
        if row and int(row[0]) == int(stat_result.st_size) and int(row[1]) == int(stat_result.st_mtime_ns):
            stable = int(row[2]) + 1
            first = str(row[3])
        else:
            stable = 1
            first = now
        db.execute(
            "INSERT OR REPLACE INTO observations(source_path,size,mtime_ns,stable_count,first_seen_utc,last_seen_utc) VALUES(?,?,?,?,?,?)",
            (key, int(stat_result.st_size), int(stat_result.st_mtime_ns), stable, first, now),
        )
        db.commit()
        return stable
    finally:
        db.close()


def _existing_ingested(digest: str) -> dict[str, Any] | None:
    db = _connect()
    try:
        row = db.execute(
            "SELECT intake_id,source_name,original_path,sha256,bytes,classification,state,target_project,patch_id,received_utc,vault_path,manifest_json,error,approved_utc,approved_root "
            "FROM intake_items WHERE sha256=? AND state IN ('AVAILABLE','CANDIDATE','LINEAGE','QUEUED','STAGED','APPLIED','CERTIFIED','REVIEW','FAILED','REJECTED') "
            "ORDER BY received_utc DESC LIMIT 1",
            (digest,),
        ).fetchone()
        if not row:
            return None
        keys = ["intake_id","source_name","original_path","sha256","bytes","classification","state","target_project","patch_id","received_utc","vault_path","manifest_json","error","approved_utc","approved_root"]
        item = dict(zip(keys, row))
        try:
            item["manifest"] = json.loads(item.pop("manifest_json"))
        except Exception:
            item["manifest"] = {}; item.pop("manifest_json", None)
        return item
    finally:
        db.close()


def _already_ingested(digest: str) -> bool:
    return _existing_ingested(digest) is not None


def _same_rejection(path: Path) -> str | None:
    try:
        st = path.stat()
        key = os.path.normcase(str(path.resolve()))
    except OSError:
        return None
    db = _connect()
    try:
        row = db.execute(
            "SELECT size,mtime_ns,error FROM rejected_observations WHERE source_path=?",
            (key,),
        ).fetchone()
        if row and int(row[0]) == int(st.st_size) and int(row[1]) == int(st.st_mtime_ns):
            return str(row[2])
        return None
    finally:
        db.close()


def _record_rejection(path: Path, error: str) -> None:
    try:
        st = path.stat()
        key = os.path.normcase(str(path.resolve()))
    except OSError:
        return
    now = utc_now()
    db = _connect()
    try:
        row = db.execute("SELECT first_seen_utc FROM rejected_observations WHERE source_path=?", (key,)).fetchone()
        first = str(row[0]) if row else now
        db.execute(
            "INSERT OR REPLACE INTO rejected_observations(source_path,size,mtime_ns,error,first_seen_utc,last_seen_utc) VALUES(?,?,?,?,?,?)",
            (key, int(st.st_size), int(st.st_mtime_ns), str(error), first, now),
        )
        db.commit()
    finally:
        db.close()

def _clear_rejection(path: Path) -> None:
    try:
        key = os.path.normcase(str(path.resolve()))
    except OSError:
        return
    db = _connect()
    try:
        db.execute("DELETE FROM rejected_observations WHERE source_path=?", (key,))
        db.commit()
    finally:
        db.close()


def _write_receipt(item: dict[str, Any]) -> Path:
    safe_project = re.sub(r"[^A-Za-z0-9._-]+", "-", str(item.get("target_project") or "unassigned")).strip("-") or "unassigned"
    folder = ensure_artifact_project_tree(safe_project)["patches"] / "receipts"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{item['intake_id']}.json"
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return path


def _persist_item(item: dict[str, Any]) -> None:
    db = _connect()
    try:
        db.execute(
            """
            INSERT INTO intake_items(
                intake_id,source_name,original_path,sha256,bytes,classification,state,
                target_project,patch_id,received_utc,vault_path,manifest_json,error,approved_utc,approved_root
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                item["intake_id"], item["source_name"], item["original_path"], item["sha256"], item["bytes"],
                item["classification"], item["state"], item["target_project"], item["patch_id"], item["received_utc"],
                item["vault_path"], json.dumps(item.get("manifest") or {}, separators=(",", ":"), sort_keys=True), item.get("error") or "",
                item.get("approved_utc") or "", item.get("approved_root") or "",
            ),
        )
        db.commit()
    finally:
        db.close()



def _safe_component(value: str, fallback: str = "unassigned") -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-.") or fallback


def _project_identity_forms(value: str) -> set[str]:
    raw = str(value or "").strip().casefold()
    if not raw:
        return set()
    forms = {raw}
    compact = re.sub(r"[^a-z0-9]+", "", raw)
    if compact:
        forms.add(compact)
    stem = re.sub(r"(?:[-_. ](?:main|master|standalone|project|repo|repository|source|src))+$", "", raw).strip("-_. ")
    if stem:
        forms.add(stem)
        compact_stem = re.sub(r"[^a-z0-9]+", "", stem)
        if compact_stem:
            forms.add(compact_stem)
    return forms


def _registered_root_for_project(project: str) -> Path | None:
    """Resolve a patch target against ForgePY's registry conservatively.

    Exact aliases win. A normalized/family alias (for example Cortex vs
    Cortex-main) is accepted only when it resolves to exactly one registered root.
    Ambiguous matches fail closed into Review.
    """
    wanted = str(project or "").strip().casefold()
    if not wanted or wanted == "unassigned":
        return None
    try:
        from PCCSurfaceCommon import ProjectRegistry
        entries = list(ProjectRegistry().entries())
        exact: list[Path] = []
        fuzzy: list[Path] = []
        wanted_forms = _project_identity_forms(wanted)
        for entry in entries:
            aliases = {entry.project_id.casefold(), entry.name.casefold(), entry.root.name.casefold()}
            try:
                from PCCProjectDiscovery import discover_project_contract_data
                data = discover_project_contract_data(entry.root)
                project_data = data.get("project") or {}
                for value in (project_data.get("id"), project_data.get("name")):
                    if value:
                        aliases.add(str(value).strip().casefold())
            except Exception:
                pass
            if wanted in aliases and entry.root.is_dir():
                exact.append(entry.root.expanduser().resolve())
                continue
            alias_forms: set[str] = set()
            for alias in aliases:
                alias_forms.update(_project_identity_forms(alias))
            if wanted_forms & alias_forms and entry.root.is_dir():
                fuzzy.append(entry.root.expanduser().resolve())
        exact_unique = list(dict.fromkeys(exact))
        if len(exact_unique) == 1:
            return exact_unique[0]
        fuzzy_unique = list(dict.fromkeys(fuzzy))
        if not exact_unique and len(fuzzy_unique) == 1:
            return fuzzy_unique[0]
    except Exception:
        return None
    return None


def _lineage_relation(details: dict[str, Any], verification: dict[str, Any] | None = None) -> str:
    if not bool(details.get("modern")):
        return "legacy"
    if not bool(details.get("buildBound")):
        return "unbound"
    if str(details.get("dateStatus") or "PASS").upper() != "PASS":
        return "date-mismatch"
    if verification is not None and verification.get("status") != "PASS":
        return "base-mismatch"
    return "historical"


def _archive_lineage_transport(
    source: Path,
    details: dict[str, Any],
    *,
    relation: str,
    remove_source: bool,
    reason: str = "",
) -> dict[str, Any]:
    """Archive one inert patch transport into project Patch Lineage.

    LINEAGE is intentionally non-executable.  It never contributes to pending update
    counts and can never be staged until the user presents the same bytes through the
    explicit incoming.patch/approval path and all live preconditions pass.
    """
    source = source.expanduser().resolve()
    digest = sha256_file(source)
    project = str(details.get("project") or "unassigned")
    patch_id = str(details.get("patchId") or f"lineage-{digest[:12]}")
    safe_project = _safe_component(project)
    safe_patch = _safe_component(patch_id, f"lineage-{digest[:12]}")
    safe_relation = _safe_component(relation, "historical")
    tree = ensure_artifact_project_tree(safe_project)
    package_dir = tree["patches"] / "lineage" / safe_relation / safe_patch
    package_dir.mkdir(parents=True, exist_ok=True)
    stored = package_dir / source.name
    if stored.exists() and sha256_file(stored) != digest:
        stored = package_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{source.name}"
    if not stored.exists():
        _promote_verified(source, stored, digest, remove_source=remove_source)
    elif remove_source:
        source.unlink(missing_ok=True)
    Path(str(stored) + ".sha256").write_text(f"{digest}  {stored.name}\n", encoding="ascii")
    manifest = details.get("manifest") if isinstance(details.get("manifest"), dict) else {}
    (package_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lineage = {
        "schema": "forge.patch.lineage.v1",
        "project": project,
        "patchId": patch_id,
        "relation": safe_relation,
        "verificationClass": details.get("verificationClass", ""),
        "packageCreatedUtc": details.get("packageCreatedUtc", ""),
        "dateStatus": details.get("dateStatus", ""),
        "sha256": digest,
        "source": str(source),
        "stored": str(stored),
        "reason": str(reason or ""),
        "catalogedUtc": utc_now(),
    }
    (package_dir / "lineage.json").write_text(json.dumps(lineage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"stored": stored, "sha256": digest, "relation": safe_relation, "lineage": lineage}


def _archive_review_transport(
    source: Path,
    details: dict[str, Any],
    *,
    reason: str,
    relation: str = "review",
    remove_source: bool = True,
) -> dict[str, Any]:
    """Retain a valid but non-executable package in actionable Review.

    Review is intentionally distinct from historical Lineage: fresh packages that
    need operator routing or whose preconditions do not currently match remain
    visible and actionable instead of disappearing into archival history.
    """
    source = source.expanduser().resolve()
    digest = sha256_file(source)
    project = str(details.get("project") or "unassigned")
    patch_id = str(details.get("patchId") or f"review-{digest[:12]}")
    tree = ensure_artifact_project_tree(_safe_component(project))
    target_dir = tree["review"] / _safe_component(relation, "review") / _safe_component(patch_id, f"review-{digest[:12]}")
    target_dir.mkdir(parents=True, exist_ok=True)
    stored = target_dir / source.name
    if stored.exists() and sha256_file(stored) != digest:
        stored = target_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{source.name}"
    if not stored.exists():
        _promote_verified(source, stored, digest, remove_source=remove_source)
    elif remove_source:
        source.unlink(missing_ok=True)
    Path(str(stored) + ".sha256").write_text(f"{digest}  {stored.name}\n", encoding="ascii")
    manifest = details.get("manifest") if isinstance(details.get("manifest"), dict) else {}
    (target_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    item = {
        "schema": "vault.intake.receipt.v1", "version": VAULT_INTAKE_VERSION,
        "intake_id": f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}",
        "source_name": source.name, "original_path": str(source),
        "sha256": digest, "bytes": int(stored.stat().st_size),
        "classification": "PATCH-ACTIONABLE-REVIEW", "state": "REVIEW",
        "target_project": project, "patch_id": patch_id, "received_utc": utc_now(),
        "vault_path": str(stored), "manifest": manifest, "error": str(reason),
        "approved_utc": "", "approved_root": "",
        "package_created_utc": details.get("packageCreatedUtc", ""),
        "date_status": details.get("dateStatus", ""),
        "verification_class": details.get("verificationClass", ""),
        "legacy_patch_id": bool(details.get("legacyPatchId")),
        "build_bound": bool(details.get("buildBound")), "relationship": relation,
    }
    _persist_item(item); _write_receipt(item)
    return item


def _queue_existing_for_project(
    root: Path,
    existing: dict[str, Any],
    *,
    classification: str,
    source_label: str,
) -> dict[str, Any]:
    """Promote already-cataloged patch evidence into the executable queue after live verification."""
    root = root.expanduser().resolve()
    manifest = existing.get("manifest") if isinstance(existing.get("manifest"), dict) else {}
    target = str(existing.get("target_project") or "")
    if target.casefold() not in _project_aliases(root):
        raise IntakeError(f"{source_label} project identity does not match the active project")
    verification = verify_manifest_preconditions(manifest, root)
    if verification.get("status") != "PASS":
        detail = "; ".join(
            f"{x.get('field')}: expected {x.get('expected')} actual {x.get('actual') or '<missing>'}"
            for x in verification.get("mismatches", [])
        )
        raise IntakeError(f"{source_label} does not match active project/build identity: " + detail)
    source = Path(str(existing.get("vault_path") or ""))
    expected = str(existing.get("sha256") or "")
    if not source.is_file() or not expected or sha256_file(source) != expected:
        raise IntakeError(f"cataloged {source_label} evidence is missing or hash-mismatched")
    approved_utc = utc_now()
    db = _connect()
    try:
        db.execute(
            "UPDATE intake_items SET state='QUEUED',classification=?,approved_utc=?,approved_root=?,error='' WHERE intake_id=?",
            (classification, approved_utc, str(root), str(existing.get("intake_id") or "")),
        )
        db.commit()
    finally:
        db.close()
    out = next(item for item in list_items() if str(item.get("intake_id")) == str(existing.get("intake_id")))
    out["buildVerification"] = verification
    return out


def _queue_existing_from_incoming(root: Path, existing: dict[str, Any]) -> dict[str, Any]:
    return _queue_existing_for_project(
        root, existing, classification="PATCH-INCOMING-APPROVED", source_label="incoming.patch"
    )


def approve_manual_patch_for_project(root: Path, source: Path) -> dict[str, Any]:
    """Explicitly approve a user-selected descriptive patch for the active project.

    This is the F60R10/F60R11 manual-selection authority.  Unlike trusted-root
    discovery it does not require the transport to be named ``incoming.patch``.
    Selection in the Forge GUI is itself the approval gesture, but every normal
    archive, project identity, date, build/source and hash check still applies.
    The original selected file is retained; Forge works from its immutable Vault copy.
    """
    root = root.expanduser().resolve()
    source = source.expanduser().resolve()
    if not source.is_file():
        raise IntakeError(f"selected patch file does not exist: {source}")

    details = inspect_patch(source)
    project = str(details.get("project") or "unassigned")
    if project.casefold() not in _project_aliases(root):
        raise IntakeError("selected patch project identity does not match the active project")
    if not bool(details.get("modern")) or not bool(details.get("buildBound")):
        raise IntakeError("selected patch must use a modern build-bound Forge/Vault patch schema")
    if str(details.get("dateStatus") or "PASS").upper() != "PASS":
        raise IntakeError(f"selected patch package date status is {details.get('dateStatus')}")

    verification = verify_manifest_preconditions(details["manifest"], root)
    if verification.get("status") != "PASS":
        detail = "; ".join(
            f"{x.get('field')}: expected {x.get('expected')} actual {x.get('actual') or '<missing>'}"
            for x in verification.get("mismatches", [])
        )
        raise IntakeError("selected patch does not match active project/build identity: " + detail)

    digest = sha256_file(source)
    existing = _existing_ingested(digest)
    if existing is not None:
        state = str(existing.get("state") or "").upper()
        if state == "APPLIED":
            raise IntakeError("selected patch is already recorded as applied")
        if state in {"QUEUED", "STAGED"}:
            out = dict(existing)
            out["buildVerification"] = verification
            return out
        if state in {"CANDIDATE", "AVAILABLE", "LINEAGE", "REVIEW"}:
            return _queue_existing_for_project(
                root, existing, classification="PATCH-MANUAL-APPROVED", source_label="selected patch"
            )

    # Catalog a new selected transport without consuming the user's source file.
    # The normal scanner stores a verified immutable Vault copy; explicit approval
    # below promotes that exact stored evidence into the queue.
    item = ingest_patch(source, remove_source=False, trusted_root=False)
    state = str(item.get("state") or "").upper()
    if state in {"CANDIDATE", "AVAILABLE"}:
        approved = approve_available_for_project(root, str(item.get("intake_id") or ""))
        db = _connect()
        try:
            db.execute(
                "UPDATE intake_items SET classification='PATCH-MANUAL-APPROVED' WHERE intake_id=?",
                (str(approved.get("intake_id") or ""),),
            )
            db.commit()
        finally:
            db.close()
        approved = next(x for x in list_items() if str(x.get("intake_id")) == str(item.get("intake_id")))
        approved["buildVerification"] = verification
        return approved
    if state == "QUEUED":
        return item
    raise IntakeError(f"selected patch could not be approved; catalog state is {state or 'UNKNOWN'}")


def ingest_patch(source: Path, *, remove_source: bool = True, trusted_root: bool = False) -> dict[str, Any]:
    source = source.expanduser().resolve()
    details = inspect_patch(source)
    digest = sha256_file(source)
    is_incoming = source.name.casefold() == INCOMING_PATCH_NAME

    existing = _existing_ingested(digest)
    if existing is not None:
        # The one deliberate project-root front door is incoming.patch. Presenting
        # identical cataloged bytes through it is explicit approval, but only after
        # the live project/build/source identity passes again.
        if trusted_root and is_incoming and str(existing.get("state") or "").upper() in {"CANDIDATE", "AVAILABLE", "LINEAGE"}:
            approved = _queue_existing_from_incoming(source.parent, existing)
            if remove_source:
                source.unlink(missing_ok=True)
                for suffix in (".sha256", ".sha256.txt"):
                    Path(str(source) + suffix).unlink(missing_ok=True)
            return approved
        # Any other duplicate is already durably represented. Consuming the duplicate
        # transport is safe and prevents Downloads/root scans from rediscovering it forever.
        if remove_source:
            source.unlink(missing_ok=True)
            for suffix in (".sha256", ".sha256.txt"):
                Path(str(source) + suffix).unlink(missing_ok=True)
        duplicate = dict(existing)
        duplicate["classification"] = "PATCH-DUPLICATE-CATALOGED"
        duplicate["duplicate"] = True
        return duplicate

    project = str(details.get("project") or "unassigned")
    verification: dict[str, Any] | None = None
    classification = "PATCH-LINEAGE"
    state = "LINEAGE"
    relation = "historical"
    approved_utc = ""
    approved_root = ""

    if trusted_root:
        # F60R9 contract: only the exact reserved incoming.patch filename is an
        # executable root transport. Arbitrary historical *.zip/*.patch files in a
        # project root are lineage evidence, never implicit queue entries.
        if not is_incoming:
            relation = "legacy-root-transport"
        else:
            aliases = _project_aliases(source.parent)
            if project.casefold() not in aliases:
                archived = _archive_lineage_transport(
                    source, details, relation="project-mismatch", remove_source=remove_source,
                    reason="incoming.patch project identity does not match active project",
                )
                item = _lineage_item(source, details, archived, error="incoming.patch project identity does not match active project")
                _persist_item(item); _write_receipt(item)
                raise IntakeError("incoming.patch project identity mismatch; package moved to Patch Lineage")
            if not bool(details.get("modern")) or not bool(details.get("buildBound")):
                archived = _archive_lineage_transport(
                    source, details, relation="unbound", remove_source=remove_source,
                    reason="incoming.patch must use a modern build-bound Forge/Vault patch schema",
                )
                item = _lineage_item(source, details, archived, error="incoming.patch is not modern/build-bound")
                _persist_item(item); _write_receipt(item)
                raise IntakeError("incoming.patch is not modern/build-bound; package moved to Patch Lineage")
            if str(details.get("dateStatus") or "PASS").upper() != "PASS":
                archived = _archive_lineage_transport(
                    source, details, relation="date-mismatch", remove_source=remove_source,
                    reason=f"incoming.patch package date status is {details.get('dateStatus')}",
                )
                item = _lineage_item(source, details, archived, error="incoming.patch package date evidence failed")
                _persist_item(item); _write_receipt(item)
                raise IntakeError("incoming.patch package date evidence failed; package moved to Patch Lineage")
            verification = verify_manifest_preconditions(details["manifest"], source.parent)
            if verification.get("status") != "PASS":
                relation = "base-mismatch"
                archived = _archive_lineage_transport(
                    source, details, relation=relation, remove_source=remove_source,
                    reason="incoming.patch does not match active build/source preconditions",
                )
                item = _lineage_item(source, details, archived, error="incoming.patch build/source preconditions do not match")
                _persist_item(item); _write_receipt(item)
                detail = "; ".join(
                    f"{x.get('field')}: expected {x.get('expected')} actual {x.get('actual') or '<missing>'}"
                    for x in verification.get("mismatches", [])
                )
                raise IntakeError("incoming.patch build/source mismatch; package moved to Patch Lineage: " + detail)
            state = "QUEUED"
            classification = "PATCH-INCOMING-APPROVED"
            relation = "descendant-candidate"
            approved_utc = utc_now()
            approved_root = str(source.parent)
    else:
        # Downloads/global watchers never create executable queue state. Fresh valid
        # packages that need attention stay in REVIEW; only clearly historical evidence
        # is sent directly to Lineage. This keeps newly downloaded Cortex/project updates
        # actionable instead of making them appear to vanish.
        relation = _lineage_relation(details)
        # Staleness is governed by package creation evidence, not the moment a user
        # copied/downloaded the file. A months-old patch downloaded five seconds ago is
        # still historical. Fall back to filesystem mtime only for legacy packages that
        # have no trustworthy package timestamp.
        age_seconds = max(0.0, time.time() - source.stat().st_mtime)
        package_created = str(details.get("packageCreatedUtc") or "").strip()
        if package_created:
            try:
                created_dt = datetime.fromisoformat(package_created.replace("Z", "+00:00"))
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                age_seconds = max(0.0, (datetime.now(timezone.utc) - created_dt.astimezone(timezone.utc)).total_seconds())
            except Exception:
                pass
        historical_age = age_seconds > 3600.0

        if project == "unassigned":
            relation = "unassigned-project"
            if not historical_age:
                return _archive_review_transport(source, details, reason="patch project is not registered/identified", relation=relation, remove_source=remove_source)
        elif bool(details.get("modern")) and bool(details.get("buildBound")) and str(details.get("dateStatus") or "PASS").upper() == "PASS":
            target_root = _registered_root_for_project(project)
            if target_root is not None:
                verification = verify_manifest_preconditions(details["manifest"], target_root)
                if verification.get("status") == "PASS":
                    state = "CANDIDATE"
                    classification = "PATCH-DESCENDANT-CANDIDATE"
                    relation = "descendant-candidate"
                else:
                    relation = "base-mismatch"
                    detail = "; ".join(
                        f"{x.get('field')}: expected {x.get('expected')} actual {x.get('actual') or '<missing>'}"
                        for x in verification.get("mismatches", [])
                    ) or "current project authority does not match package preconditions"
                    if not historical_age:
                        return _archive_review_transport(source, details, reason=detail, relation=relation, remove_source=remove_source)
            else:
                # A current modern package for a project not yet registered with this
                # ForgePY instance stays globally discoverable as a non-executable
                # candidate. It can later be routed once the project is registered.
                state = "CANDIDATE"
                classification = "PATCH-UNVERIFIED-CANDIDATE"
                relation = "unregistered-project"
        # Legacy/unbound/date-failed transports remain historical evidence. They are
        # retained in Lineage rather than promoted merely because they were downloaded
        # recently.

    if state == "LINEAGE":
        archived = _archive_lineage_transport(source, details, relation=relation, remove_source=remove_source)
        item = _lineage_item(source, details, archived)
        _persist_item(item); _write_receipt(item)
        if remove_source:
            for suffix in (".sha256", ".sha256.txt"):
                Path(str(source) + suffix).unlink(missing_ok=True)
        return item

    intake_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}"
    quarantine = vault_root() / "intake" / "quarantine" / intake_id
    quarantine.mkdir(parents=True, exist_ok=True)
    staged = quarantine / source.name
    temp = quarantine / (source.name + ".copying")
    shutil.copy2(source, temp)
    if sha256_file(temp) != digest:
        temp.unlink(missing_ok=True)
        raise IntakeError("Forge quarantine copy hash mismatch")
    os.replace(temp, staged)

    safe_project = _safe_component(project)
    safe_patch = _safe_component(str(details.get("patchId") or intake_id), intake_id)
    tree = ensure_artifact_project_tree(safe_project)
    bucket = "queued" if state == "QUEUED" else "candidates"
    package_dir = tree["patches"] / bucket / safe_patch
    package_dir.mkdir(parents=True, exist_ok=True)
    stored = package_dir / source.name
    if stored.exists():
        stored = package_dir / f"{intake_id}_{source.name}"
    _promote_verified(staged, stored, digest, remove_source=True)
    Path(str(stored) + ".sha256").write_text(f"{digest}  {stored.name}\n", encoding="ascii")
    (package_dir / "manifest.json").write_text(json.dumps(details["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        quarantine.rmdir()
    except OSError:
        pass

    item = {
        "schema": "vault.intake.receipt.v1", "version": VAULT_INTAKE_VERSION,
        "intake_id": intake_id, "source_name": source.name, "original_path": str(source),
        "sha256": digest, "bytes": int(source.stat().st_size), "classification": classification,
        "state": state, "target_project": project, "patch_id": details["patchId"], "received_utc": utc_now(),
        "vault_path": str(stored), "manifest": details["manifest"], "error": "",
        "approved_utc": approved_utc, "approved_root": approved_root,
        "package_created_utc": details.get("packageCreatedUtc", ""), "date_status": details.get("dateStatus", ""),
        "verification_class": details.get("verificationClass", ""), "legacy_patch_id": bool(details.get("legacyPatchId")),
        "build_bound": bool(details.get("buildBound")), "relationship": relation,
    }
    _persist_item(item); _write_receipt(item)
    if remove_source:
        source.unlink(missing_ok=True)
        for suffix in (".sha256", ".sha256.txt"):
            Path(str(source) + suffix).unlink(missing_ok=True)
    return item


def _lineage_item(source: Path, details: dict[str, Any], archived: dict[str, Any], *, error: str = "") -> dict[str, Any]:
    intake_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}"
    return {
        "schema": "vault.intake.receipt.v1", "version": VAULT_INTAKE_VERSION,
        "intake_id": intake_id, "source_name": source.name, "original_path": str(source),
        "sha256": str(archived.get("sha256") or ""), "bytes": int(Path(str(archived.get("stored"))).stat().st_size),
        "classification": "PATCH-LINEAGE", "state": "LINEAGE",
        "target_project": str(details.get("project") or "unassigned"),
        "patch_id": str(details.get("patchId") or f"lineage-{str(archived.get('sha256') or '')[:12]}"),
        "received_utc": utc_now(), "vault_path": str(archived.get("stored") or ""),
        "manifest": details.get("manifest") if isinstance(details.get("manifest"), dict) else {},
        "error": str(error or ""), "approved_utc": "", "approved_root": "",
        "package_created_utc": details.get("packageCreatedUtc", ""), "date_status": details.get("dateStatus", ""),
        "verification_class": details.get("verificationClass", ""), "legacy_patch_id": bool(details.get("legacyPatchId")),
        "build_bound": bool(details.get("buildBound")), "relationship": str(archived.get("relation") or "historical"),
    }

def _archive_global_rejected_transport(path: Path, *, reason: str, remove_source: bool) -> dict[str, Any] | None:
    """Retain rejected Downloads packages as inert lineage when project attribution is known."""
    if not remove_source or not path.is_file():
        return None
    project = identify_project(path) or "unassigned"
    if project != "unassigned":
        try:
            digest = sha256_file(path)
            details = {
                "project": project,
                "patchId": f"invalid-{digest[:12]}",
                "manifest": {},
                "verificationClass": "INVALID",
                "packageCreatedUtc": "",
                "dateStatus": "INVALID",
                "modern": False,
                "buildBound": False,
                "legacyPatchId": False,
            }
            archived = _archive_lineage_transport(path, details, relation="invalid", remove_source=True, reason=reason)
            item = _lineage_item(path, details, archived, error=str(reason))
            item["classification"] = "PATCH-LINEAGE-INVALID"
            _persist_item(item); _write_receipt(item)
            for suffix in (".sha256", ".sha256.txt"):
                Path(str(path) + suffix).unlink(missing_ok=True)
            return item
        except Exception:
            pass
    try:
        receipt = archive_artifact_file(
            path, "unassigned", category="review", move=True,
            metadata={
                "artifactType": "rejected-patch-transport",
                "intakeDisposition": "REVIEW-NONEXECUTABLE",
                "reason": str(reason),
                "sourceMtimeUtc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat() if path.exists() else "",
                "intakeUtc": utc_now(),
            },
        )
    except Exception:
        return None
    digest = str(receipt.get("sha256") or "")
    intake_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}"
    item = {
        "schema": "vault.intake.receipt.v1", "version": VAULT_INTAKE_VERSION,
        "intake_id": intake_id, "source_name": path.name, "original_path": str(path),
        "sha256": digest, "bytes": int(receipt.get("bytes", 0) or 0),
        "classification": "PATCH-REJECTED-REVIEW", "state": "REVIEW",
        "target_project": "unassigned", "patch_id": f"review-{digest[:12]}" if digest else f"review-{uuid.uuid4().hex[:12]}",
        "received_utc": utc_now(), "vault_path": str(receipt.get("artifactPath") or ""), "manifest": {},
        "error": str(reason), "approved_utc": "", "approved_root": "",
    }
    try:
        _persist_item(item); _write_receipt(item)
    except Exception:
        pass
    return item

def scan_roots(roots: Iterable[Path], *, force_stable: bool = False, remove_source: bool = True, trusted_roots: Iterable[Path] = ()) -> dict[str, Any]:
    """Scan top-level trusted intake roots for patches and recognized project artifacts.

    Global locations are intentionally conservative: non-patch files are only moved when
    both their artifact class and registered project identity are unambiguous.  A project
    root itself provides the project identity.  Unknown Downloads content is never moved.
    """
    results: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    scanned_roots: list[str] = []
    seen_paths: set[str] = set()
    intake_settings = load_settings().get("intake") or {}
    archive_nonpatch = bool(intake_settings.get("archiveNonPatchArtifacts", True))
    stable_seconds = float(intake_settings.get("stabilitySeconds", DEFAULT_STABLE_SECONDS) or DEFAULT_STABLE_SECONDS)
    cold_stable_seconds = max(stable_seconds, float(intake_settings.get("coldStableSeconds", 10.0) or 10.0))
    trusted_keys: set[str] = set()
    for value in trusted_roots:
        try: trusted_keys.add(os.path.normcase(str(value.expanduser().resolve())))
        except Exception: trusted_keys.add(os.path.normcase(str(value.expanduser())))

    for root in roots:
        root = root.expanduser()
        if not root.is_dir():
            continue
        try:
            resolved_root = root.resolve()
        except Exception:
            resolved_root = root
        scanned_roots.append(str(resolved_root))
        for path in sorted(root.iterdir()):
            if not path.is_file() or path.suffix.casefold() in TEMP_SUFFIXES:
                continue
            try:
                key = os.path.normcase(str(path.resolve()))
            except Exception:
                key = os.path.normcase(str(path))
            if key in seen_paths:
                continue
            seen_paths.add(key)

            is_trusted_root = os.path.normcase(str(resolved_root)) in trusted_keys
            is_patch_transport = looks_like_patch(path)
            suffix = path.suffix.casefold()
            is_named_patch = suffix in PATCH_SUFFIXES and (
                path.name.casefold() == INCOMING_PATCH_NAME
                or (bool(PATCH_NAME_RE.search(path.name)) and not bool(NON_PATCH_RE.search(path.name)))
            )
            if not is_patch_transport and not is_named_patch:
                # A trusted project/application root is source authority, not an artifact
                # inbox.  Never relocate manifests, reports, builds, or other normal project
                # files merely because they resemble an Artifact Central category.  Trusted
                # roots contribute only deliberate patch transports.
                if is_trusted_root:
                    continue
                if not archive_nonpatch or not auto_archive_candidate(path):
                    continue
                project = identify_project(path, root_hint=resolved_root)
                if not project:
                    skipped.append({"path": str(path), "reason": "recognized artifact has no unambiguous registered project identity"})
                    continue
                try:
                    age = max(0.0, time.time() - path.stat().st_mtime)
                    stable_count = _observe(path)
                    if not force_stable and (age < stable_seconds or (stable_count < 2 and age < cold_stable_seconds)):
                        skipped.append({"path": str(path), "reason": "waiting for artifact to stabilize"})
                        continue
                    category = classify_artifact(path)
                    receipt = archive_artifact_file(
                        path,
                        project,
                        category=category,
                        move=remove_source,
                        metadata={
                            "sourceRoot": str(resolved_root),
                            "sourceMtimeUtc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
                            "intakeUtc": utc_now(),
                            "classificationAuthority": "VaultArtifacts",
                        },
                    )
                    receipt["source_name"] = path.name
                    receipt["project_id"] = project
                    artifacts.append(receipt)
                except Exception as exc:
                    errors.append({"path": str(path), "error": f"artifact archive failed: {exc}"})
                continue

            previous = _same_rejection(path)
            if previous is not None:
                skipped.append({"path": str(path), "reason": f"unchanged previously rejected transport: {previous}"})
                continue
            try:
                age = max(0.0, time.time() - path.stat().st_mtime)
                stable_count = _observe(path)
                if not force_stable and (age < stable_seconds or (stable_count < 2 and age < cold_stable_seconds)):
                    skipped.append({"path": str(path), "reason": "waiting for patch transport to stabilize"})
                    continue
                item = ingest_patch(path, remove_source=remove_source, trusted_root=os.path.normcase(str(resolved_root)) in trusted_keys)
                _clear_rejection(path)
                results.append(item)
            except IntakeError as exc:
                message = str(exc)
                if "byte-identical patch is already queued/applied" in message:
                    skipped.append({"path": str(path), "reason": message})
                    _record_rejection(path, message)
                elif not is_trusted_root:
                    reviewed = _archive_global_rejected_transport(path, reason=message, remove_source=remove_source)
                    if reviewed is not None:
                        reviews.append(reviewed)
                        _clear_rejection(path)
                    else:
                        skipped.append({"path": str(path), "reason": f"global patch candidate retained for review: {message}"})
                        _record_rejection(path, message)
                else:
                    errors.append({"path": str(path), "error": message})
                    _record_rejection(path, message)
            except Exception as exc:
                message = str(exc)
                if not is_trusted_root:
                    reviewed = _archive_global_rejected_transport(path, reason=message, remove_source=remove_source)
                    if reviewed is not None:
                        reviews.append(reviewed)
                        _clear_rejection(path)
                    else:
                        skipped.append({"path": str(path), "reason": f"global patch candidate retained for review: {message}"})
                        _record_rejection(path, message)
                else:
                    errors.append({"path": str(path), "error": message})
                    _record_rejection(path, message)
    return {
        "schema": "vault.intake.scan.v1",
        "version": VAULT_INTAKE_VERSION,
        "timestampUtc": utc_now(),
        "roots": scanned_roots,
        "ingested": results,
        "artifacts": artifacts,
        "reviews": reviews,
        "skipped": skipped,
        "errors": errors,
    }


def scan_downloads(*, force_stable: bool = False, remove_source: bool = True) -> dict[str, Any]:
    # Repair stale pre-F60R9 queue state before cataloging anything new. Downloads
    # itself remains discovery/lineage authority only.
    normalize_queue_authority()
    return scan_roots(downloads_roots(), force_stable=force_stable, remove_source=remove_source)


def scan_intake(*, extra_roots: Sequence[Path] = (), force_stable: bool = False, remove_source: bool = True) -> dict[str, Any]:
    return scan_roots(intake_roots(extra_roots), force_stable=force_stable, remove_source=remove_source, trusted_roots=extra_roots)

def list_items(*, state: str | None = None, project: str | None = None) -> list[dict[str, Any]]:
    db = _connect()
    try:
        sql = "SELECT intake_id,source_name,original_path,sha256,bytes,classification,state,target_project,patch_id,received_utc,vault_path,manifest_json,error,approved_utc,approved_root FROM intake_items"
        where: list[str] = []
        args: list[Any] = []
        if state:
            where.append("state=?"); args.append(state.upper())
        if project:
            where.append("lower(target_project)=lower(?)"); args.append(project)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY received_utc DESC"
        rows = db.execute(sql, args).fetchall()
        keys = ["intake_id","source_name","original_path","sha256","bytes","classification","state","target_project","patch_id","received_utc","vault_path","manifest_json","error","approved_utc","approved_root"]
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(zip(keys, row))
            try:
                item["manifest"] = json.loads(item.pop("manifest_json"))
            except Exception:
                item["manifest"] = {}; item.pop("manifest_json", None)
            out.append(item)
        return out
    finally:
        db.close()


def _origin_is_global_download(path_value: str) -> bool:
    raw = str(path_value or "").strip()
    if not raw:
        return False
    try:
        candidate = Path(raw).expanduser().resolve()
    except Exception:
        candidate = Path(raw).expanduser()
    for folder in downloads_roots():
        try:
            candidate.relative_to(folder.expanduser().resolve())
            return True
        except Exception:
            continue
    return False


def available_for_project(root: Path, *, compatible_only: bool = True) -> list[dict[str, Any]]:
    """Return non-executable descendant candidates for the selected project.

    Compatibility note: F60R8 used AVAILABLE.  Those rows are accepted here only so
    they can be live-verified and migrated; new scans create CANDIDATE or LINEAGE.
    """
    root = root.expanduser().resolve()
    aliases = _project_aliases(root)
    matches: list[dict[str, Any]] = []
    for item in [x for x in list_items() if str(x.get("state") or "").upper() in {"CANDIDATE", "AVAILABLE"}]:
        if str(item.get("target_project") or "").casefold() not in aliases:
            continue
        manifest = item.get("manifest") if isinstance(item.get("manifest"), dict) else {}
        verification = verify_manifest_preconditions(manifest, root)
        enriched = dict(item)
        enriched["buildVerification"] = verification
        if compatible_only and verification.get("status") != "PASS":
            continue
        matches.append(enriched)
    return matches


def approve_available_for_project(root: Path, intake_id: str) -> dict[str, Any]:
    """Explicitly authorize one cataloged descendant candidate for execution."""
    root = root.expanduser().resolve()
    selected = next(
        (item for item in list_items() if str(item.get("intake_id")) == str(intake_id) and str(item.get("state") or "").upper() in {"CANDIDATE", "AVAILABLE"}),
        None,
    )
    if selected is None:
        raise IntakeError("selected downloaded patch is not an executable candidate")
    aliases = _project_aliases(root)
    if str(selected.get("target_project") or "").casefold() not in aliases:
        raise IntakeError("downloaded patch does not target the active project")
    source = Path(str(selected.get("vault_path") or ""))
    if not source.is_file():
        raise IntakeError(f"cataloged downloaded patch is missing: {source}")
    expected = str(selected.get("sha256") or "")
    if not expected or sha256_file(source) != expected:
        raise IntakeError("cataloged downloaded patch hash mismatch")
    manifest = selected.get("manifest") if isinstance(selected.get("manifest"), dict) else {}
    verification = verify_manifest_preconditions(manifest, root)
    if verification.get("status") != "PASS":
        detail = "; ".join(
            f"{x.get('field')}: expected {x.get('expected')} actual {x.get('actual') or '<missing>'}"
            for x in verification.get("mismatches", [])
        )
        # A package that no longer matches current authority is historical lineage,
        # not a failed/pending update.
        _relocate_catalog_item_to_lineage(
            selected, "base-mismatch",
            error="candidate base no longer matches current authority: " + detail,
        )
        raise IntakeError("downloaded patch no longer matches active project/build identity; moved to Patch Lineage: " + detail)
    approved_utc = utc_now()
    db = _connect()
    try:
        db.execute(
            "UPDATE intake_items SET state='QUEUED',classification='PATCH-EXPLICITLY-APPROVED',approved_utc=?,approved_root=?,error='' WHERE intake_id=? AND state IN ('CANDIDATE','AVAILABLE')",
            (approved_utc, str(root), str(intake_id)),
        )
        if db.total_changes != 1:
            raise IntakeError("downloaded patch approval raced with another intake action")
        db.commit()
    finally:
        db.close()
    approved = next(item for item in list_items() if str(item.get("intake_id")) == str(intake_id))
    safe_project = _safe_component(str(approved.get("target_project") or "unassigned"))
    receipt_dir = ensure_artifact_project_tree(safe_project)["patches"] / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt = receipt_dir / f"approval-{intake_id}.json"
    payload = {
        "schema": "forge.patch.approval.v1", "intakeId": str(intake_id),
        "patchId": approved.get("patch_id"), "project": approved.get("target_project"),
        "approvedUtc": approved_utc, "approvedRoot": str(root), "sha256": expected,
        "buildVerification": verification, "source": str(source),
    }
    temp = receipt.with_suffix(receipt.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, receipt)
    approved["approvalReceipt"] = str(receipt)
    approved["buildVerification"] = verification
    return approved


def _authorized_queue_item(item: dict[str, Any], root: Path | None = None) -> bool:
    state = str(item.get("state") or "").upper()
    if state not in {"QUEUED", "STAGED"}:
        return False
    if str(item.get("approved_utc") or "").strip() and str(item.get("approved_root") or "").strip():
        if root is None:
            return True
        try:
            return Path(str(item.get("approved_root"))).expanduser().resolve() == root.expanduser().resolve()
        except Exception:
            return False
    # No approval evidence means a pre-F60R9 queue row. It is never executable.
    return False


def _relocate_catalog_item_to_lineage(item: dict[str, Any], relation: str, *, error: str = "") -> None:
    intake_id = str(item.get("intake_id") or "")
    source = Path(str(item.get("vault_path") or ""))
    project = _safe_component(str(item.get("target_project") or "unassigned"))
    patch_id = _safe_component(str(item.get("patch_id") or intake_id), intake_id or "lineage")
    target_dir = ensure_artifact_project_tree(project)["patches"] / "lineage" / _safe_component(relation, "historical") / patch_id
    new_path = source
    try:
        if source.is_file():
            source_dir = source.parent
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            final_dir = target_dir
            if final_dir.exists() and source_dir.resolve() != final_dir.resolve():
                final_dir = target_dir.with_name(target_dir.name + "-" + (intake_id[-6:] or uuid.uuid4().hex[:6]))
            if source_dir.resolve() != final_dir.resolve():
                shutil.move(str(source_dir), str(final_dir))
            new_path = final_dir / source.name
    except Exception:
        new_path = source
    _set_item_state(intake_id, "LINEAGE", vault_path_value=str(new_path), error=error)


def review_items() -> list[dict[str, Any]]:
    """Return every actionable non-executable download/review item globally.

    CANDIDATE means the package is structurally current but has not received explicit
    execution authority. REVIEW means operator routing/compatibility attention is
    required. Both belong in the same decision surface.
    """
    return [item for item in list_items() if str(item.get("state") or "").upper() in {"REVIEW", "CANDIDATE"}]


def reevaluate_review_item(intake_id: str, root: Path) -> dict[str, Any]:
    """Re-check a reviewed patch against an explicitly selected project root."""
    root = root.expanduser().resolve()
    item = next((x for x in list_items() if str(x.get("intake_id")) == str(intake_id) and str(x.get("state") or "").upper() in {"REVIEW", "CANDIDATE", "LINEAGE"}), None)
    if item is None:
        raise IntakeError("review item no longer exists")
    return _queue_existing_for_project(root, item, classification="PATCH-REVIEW-APPROVED", source_label="reviewed patch")



def retarget_review_item(intake_id: str, target_project: str) -> dict[str, Any]:
    """Change Review routing without granting execution authority.

    The operator may correct a filename/alias classification here. The package remains
    REVIEW/CANDIDATE until separately re-evaluated and approved against that project's
    actual root/build/source preconditions.
    """
    target_project = str(target_project or "").strip()
    if not target_project:
        raise IntakeError("target project is required")
    item = next((x for x in list_items() if str(x.get("intake_id")) == str(intake_id) and str(x.get("state") or "").upper() in {"REVIEW", "CANDIDATE"}), None)
    if item is None:
        raise IntakeError("review item no longer exists")
    with _connect() as db:
        db.execute(
            "UPDATE intake_items SET target_project=?, error=? WHERE intake_id=?",
            (target_project, f"operator routed to {target_project}; approval still required", str(intake_id)),
        )
        db.commit()
    updated = next(x for x in list_items() if str(x.get("intake_id")) == str(intake_id))
    _write_receipt(updated)
    return updated

def archive_review_item(intake_id: str, *, relation: str = "operator-archived") -> dict[str, Any]:
    item = next((x for x in list_items() if str(x.get("intake_id")) == str(intake_id) and str(x.get("state") or "").upper() in {"REVIEW", "CANDIDATE"}), None)
    if item is None:
        raise IntakeError("review item no longer exists")
    _relocate_catalog_item_to_lineage(item, relation, error=str(item.get("error") or "archived from Review"))
    return next(x for x in list_items() if str(x.get("intake_id")) == str(intake_id))


def ignore_review_item(intake_id: str) -> dict[str, Any]:
    item = next((x for x in list_items() if str(x.get("intake_id")) == str(intake_id) and str(x.get("state") or "").upper() in {"REVIEW", "CANDIDATE"}), None)
    if item is None:
        raise IntakeError("review item no longer exists")
    _set_item_state(str(intake_id), "IGNORED", error=str(item.get("error") or "ignored by operator"))
    return next(x for x in list_items() if str(x.get("intake_id")) == str(intake_id))


def normalize_queue_authority(root: Path | None = None) -> dict[str, Any]:
    """Repair legacy queue rows so discovery can never become execution authority.

    F60R8 and earlier builds could leave QUEUED/STAGED rows without durable approval
    evidence.  F60R9 demotes every such row to LINEAGE.  This is intentionally
    idempotent and is called before health counts and staging.
    """
    changed: list[dict[str, Any]] = []
    for item in list_items():
        state = str(item.get("state") or "").upper()
        if state not in {"QUEUED", "STAGED", "AVAILABLE"}:
            continue
        if state == "AVAILABLE":
            # Reclassify old Downloads rows against current project authority.  An
            # outdated package becomes lineage immediately rather than lingering as
            # a misleading update candidate.
            manifest = item.get("manifest") if isinstance(item.get("manifest"), dict) else {}
            schema = str(manifest.get("schema") or "").casefold()
            modern = schema.startswith("vault.patch.v2") or schema.startswith("forge.patch.v1")
            declared = {}
            for key in ("requires", "preconditions", "targetBuild"):
                value = manifest.get(key)
                if isinstance(value, dict):
                    declared.update(value)
            bound = any(declared.get(k) not in (None, "") for k in (
                "gitCommit","gitHead","commit","sourceCommit","projectVersion","version","targetVersion",
                "projectBuild","build","buildId","baseline","greenId","gateId","green"
            ))
            target_root = _registered_root_for_project(str(item.get("target_project") or ""))
            next_state = "CANDIDATE"
            reason = "migrated from pre-F60R9 AVAILABLE state"
            if not modern or not bound:
                next_state = "LINEAGE"
                reason = "legacy/unbound pre-F60R9 Downloads entry moved to Patch Lineage"
            elif target_root is not None:
                verification = verify_manifest_preconditions(manifest, target_root)
                if verification.get("status") != "PASS":
                    next_state = "LINEAGE"
                    reason = "pre-F60R9 Downloads entry no longer matches current project authority"
            if next_state == "LINEAGE":
                _relocate_catalog_item_to_lineage(item, "migrated-historical", error=reason)
            else:
                _set_item_state(str(item.get("intake_id") or ""), next_state, error=reason)
            changed.append({"patchId": item.get("patch_id"), "from": "AVAILABLE", "to": next_state})
            continue
        if _authorized_queue_item(item, root):
            continue
        # Never delete arbitrary project files.  If an old STAGED copy can be proven
        # byte-identical to Forge's catalog entry, remove only that compatibility copy.
        if state == "STAGED":
            target_root = root or _registered_root_for_project(str(item.get("target_project") or ""))
            if target_root is not None:
                for name in {str(item.get("source_name") or ""), "incoming.zip"}:
                    if not name:
                        continue
                    staged = target_root / "updates" / "inbox" / name
                    try:
                        if staged.is_file() and sha256_file(staged) == str(item.get("sha256") or ""):
                            staged.unlink(missing_ok=True)
                            Path(str(staged) + ".sha256").unlink(missing_ok=True)
                    except Exception:
                        pass
        _relocate_catalog_item_to_lineage(
            item, "unauthorized-legacy-queue",
            error="pre-F60R9 queue lacked explicit approval evidence; demoted to Patch Lineage",
        )
        changed.append({"patchId": item.get("patch_id"), "from": state, "to": "LINEAGE"})
    return {"normalized": len(changed), "items": changed}

def counts_for_project(*names: str) -> tuple[int, int]:
    """Return executable queue counts only.

    Discovery/candidate/lineage states never count as pending updates.  A queue row
    must carry explicit approval evidence; stale pre-F60R9 rows are normalized away.
    """
    normalize_queue_authority()
    wanted = {name.strip().casefold() for name in names if name and name.strip()}
    db = _connect()
    try:
        rows = db.execute(
            "SELECT intake_id,target_project,state,error,approved_utc,approved_root FROM intake_items WHERE state IN ('QUEUED','STAGED','REJECTED','FAILED')"
        ).fetchall()
    finally:
        db.close()
    pending = invalid = 0
    for intake_id, project, state, error, approved_utc, approved_root in rows:
        project_key = str(project or "").casefold()
        if wanted and project_key not in wanted:
            continue
        upper = str(state or "").upper()
        if upper in {"QUEUED", "STAGED"}:
            if not str(approved_utc or "").strip() or not str(approved_root or "").strip():
                continue
            pending += 1
        else:
            invalid += 1
    return pending, invalid

def _project_aliases(root: Path) -> set[str]:
    raw_aliases = {root.name.casefold()}
    try:
        from PCCProjectDiscovery import discover_project_contract_data
        data = discover_project_contract_data(root)
        project = data.get("project") or {}
        for value in (project.get("id"), project.get("name")):
            if value:
                raw_aliases.add(str(value).strip().casefold())
    except Exception:
        pass
    if "forgepy" in raw_aliases or "forge-project-control-center" in raw_aliases or (root / "app" / "ForgePYVersion.py").is_file() or (root / "app" / "ForgeVersion.py").is_file():
        raw_aliases.update({"forgepy", "forge-py", "forge", "vault", "vault-project-control-center", "forge-project-control-center"})
    aliases: set[str] = set()
    for value in raw_aliases:
        aliases.update(_project_identity_forms(value))
    return {x for x in aliases if x}


def _set_item_state(intake_id: str, state: str, *, vault_path_value: str | None = None, error: str = "") -> None:
    db = _connect()
    try:
        if vault_path_value is None:
            db.execute("UPDATE intake_items SET state=?,error=? WHERE intake_id=?", (state, error, intake_id))
        else:
            db.execute("UPDATE intake_items SET state=?,vault_path=?,error=? WHERE intake_id=?", (state, vault_path_value, error, intake_id))
        db.commit()
    finally:
        db.close()


def stage_for_project(root: Path, *, compatibility_inbox: bool = False) -> dict[str, Any]:
    """Validate explicitly approved queue items for one project.

    Canonical Forge patches stay in Artifact Central and are applied from there.
    `compatibility_inbox=True` is reserved for legacy project-native patch authorities
    that still require updates/inbox.  Discovery alone can never reach this function.
    """
    root = root.expanduser().resolve()
    normalize_queue_authority(root)
    aliases = _project_aliases(root)
    items = [item for item in list_items() if str(item.get("state") or "").upper() in {"QUEUED", "STAGED"}]
    selected = [
        item for item in items
        if str(item.get("target_project") or "").casefold() in aliases and _authorized_queue_item(item, root)
    ]
    if not selected:
        return {"staged": 0, "items": [], "root": str(root), "compatibilityInbox": bool(compatibility_inbox)}

    staged_rows: list[dict[str, Any]] = []
    inbox = root / "updates" / "inbox"
    if compatibility_inbox:
        inbox.mkdir(parents=True, exist_ok=True)

    for item in selected:
        source = Path(str(item.get("vault_path") or ""))
        if not source.is_file():
            _set_item_state(str(item.get("intake_id") or ""), "FAILED", error="approved Forge transport missing")
            raise IntakeError(f"approved Forge transport missing: {source}")
        expected = str(item.get("sha256") or "")
        if not expected or sha256_file(source) != expected:
            _set_item_state(str(item.get("intake_id") or ""), "FAILED", error="approved Forge transport hash mismatch")
            raise IntakeError(f"approved Forge transport hash mismatch: {source}")
        manifest = item.get("manifest") if isinstance(item.get("manifest"), dict) else {}
        verification = verify_manifest_preconditions(manifest, root)
        if verification.get("status") != "PASS":
            detail = "; ".join(
                f"{x.get('field')}: expected {x.get('expected')} actual {x.get('actual') or '<missing>'}"
                for x in verification.get("mismatches", [])
            )
            # Authority moved after approval. This is no longer a pending/failing
            # update; it is historical lineage evidence.
            _relocate_catalog_item_to_lineage(
                item, "base-mismatch",
                error="approved patch base no longer matches: " + detail,
            )
            raise IntakeError("approved patch no longer matches active project/build identity; demoted to Patch Lineage: " + detail)

        project_inbox = ""
        if compatibility_inbox:
            logical_name = str(item.get("source_name") or source.name)
            staged_name = "incoming.zip" if logical_name.casefold() == INCOMING_PATCH_NAME else logical_name
            dest = inbox / staged_name
            if dest.exists():
                if sha256_file(dest) != expected:
                    raise IntakeError(f"project compatibility inbox already contains conflicting transport: {dest.name}")
            else:
                temp = inbox / (staged_name + ".forge-copying")
                shutil.copy2(source, temp)
                if sha256_file(temp) != expected:
                    temp.unlink(missing_ok=True)
                    raise IntakeError(f"project compatibility inbox copy hash mismatch: {source.name}")
                os.replace(temp, dest)
            Path(str(dest) + ".sha256").write_text(f"{expected}  {dest.name}\n", encoding="ascii")
            project_inbox = str(dest)

        _set_item_state(str(item.get("intake_id") or ""), "STAGED")
        staged_rows.append({
            "intakeId": item.get("intake_id"), "patchId": item.get("patch_id"),
            "source": str(source), "projectInbox": project_inbox,
            "buildVerification": verification,
        })
    return {"staged": len(staged_rows), "items": staged_rows, "root": str(root), "compatibilityInbox": bool(compatibility_inbox)}

def _applied_patch_ids(root: Path) -> set[str]:
    folders = [
        root / "artifacts" / "patches" / "receipts",
        root / "updates" / "receipts",
        root / ".project_control" / "receipts",
        root / ".cortex" / "patches" / "receipts",
    ]
    found: set[str] = set()
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            state = str(data.get("status") or data.get("result") or "").casefold()
            if state not in {"applied", "pass", "success", "green"}:
                continue
            patch_id = str(data.get("patchId") or data.get("patch_id") or "").strip()
            if patch_id:
                found.add(patch_id.casefold())
    return found


def reconcile_project(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    aliases = _project_aliases(root)
    applied = _applied_patch_ids(root)
    if not applied:
        return {"reconciled": 0, "items": [], "root": str(root)}
    changed: list[dict[str, Any]] = []
    for item in list_items():
        if item.get("state") not in {"QUEUED", "STAGED"}:
            continue
        if str(item.get("target_project") or "").casefold() not in aliases:
            continue
        if str(item.get("patch_id") or "").casefold() not in applied:
            continue
        source = Path(str(item["vault_path"]))
        safe_project = re.sub(r"[^A-Za-z0-9._-]+", "-", str(item["target_project"])).strip("-") or "unassigned"
        target_dir = ensure_artifact_project_tree(safe_project)["patches"] / "applied" / re.sub(r"[^A-Za-z0-9._-]+", "-", str(item["patch_id"])).strip("-")
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        source_dir = source.parent
        if source_dir.exists():
            if target_dir.exists():
                target_dir = target_dir.with_name(target_dir.name + "-" + str(item["intake_id"])[-6:])
            shutil.move(str(source_dir), str(target_dir))
            new_path = target_dir / source.name
        else:
            new_path = source
        _set_item_state(str(item["intake_id"]), "APPLIED", vault_path_value=str(new_path))
        changed.append({"patchId": item["patch_id"], "vaultPath": str(new_path)})
    return {"reconciled": len(changed), "items": changed, "root": str(root)}


def watch(*, interval: float = 3.0) -> int:
    try:
        while True:
            result = scan_downloads()
            for item in result["ingested"]:
                state = str(item.get("state") or "CATALOGED").upper()
                print(f"[INFO] {state} {item['patch_id']} -> {item['vault_path']}", flush=True)
            for item in result["errors"]:
                print(f"[WARN] intake rejected {item['path']}: {item['error']}", flush=True)
            time.sleep(max(1.0, interval))
    except KeyboardInterrupt:
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vault Downloads/Vault intake service")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--force-stable", action="store_true")
    scan.add_argument("--keep-source", action="store_true")
    watch_p = sub.add_parser("watch")
    watch_p.add_argument("--interval", type=float, default=3.0)
    list_p = sub.add_parser("list")
    list_p.add_argument("--state")
    list_p.add_argument("--project")
    ns = parser.parse_args(argv)
    if ns.command == "scan":
        payload = scan_downloads(force_stable=ns.force_stable, remove_source=not ns.keep_source)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if payload["errors"] else 0
    if ns.command == "watch":
        return watch(interval=ns.interval)
    print(json.dumps(list_items(state=ns.state, project=ns.project), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
