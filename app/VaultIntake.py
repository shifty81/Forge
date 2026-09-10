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

VAULT_INTAKE_VERSION = "FORGE-INTAKE-0.4.6"
TEMP_SUFFIXES = {".crdownload", ".part", ".download", ".tmp"}
NON_PATCH_RE = re.compile(r"(?:debugbundle|debug[-_ ]?bundle|handoff|source[-_ ]?(?:rollup|bundle)|rollup|backup|support[-_ ]?bundle|archive)", re.I)
PATCH_NAME_RE = re.compile(r"(?:root[-_ ]?patch|rootpatch|incremental[-_ ]?patch|patch[-_ ]?update|[_-]patch[_-]|^patch[_-])", re.I)
PATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
MAX_FILES = 5000
MAX_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
MAX_SINGLE_FILE = 512 * 1024 * 1024
MAX_PATH_CHARS = 260
DEFAULT_STABLE_SECONDS = 2.0


class IntakeError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
            error TEXT NOT NULL
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
    if path.suffix.casefold() != ".zip":
        raise IntakeError("not a ZIP transport")
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
    schema = str(manifest.get("schema") or "").strip()
    modern = schema.casefold().startswith("vault.patch.v2")
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
        "manifest": manifest,
    }


def looks_like_patch(path: Path) -> bool:
    if not path.is_file() or path.suffix.casefold() != ".zip":
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


def _already_ingested(digest: str) -> bool:
    db = _connect()
    try:
        row = db.execute(
            "SELECT 1 FROM intake_items WHERE sha256=? AND state IN ('AVAILABLE','QUEUED','STAGED','APPLIED','CERTIFIED','REVIEW') LIMIT 1",
            (digest,),
        ).fetchone()
        return bool(row)
    finally:
        db.close()


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
                target_project,patch_id,received_utc,vault_path,manifest_json,error
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                item["intake_id"], item["source_name"], item["original_path"], item["sha256"], item["bytes"],
                item["classification"], item["state"], item["target_project"], item["patch_id"], item["received_utc"],
                item["vault_path"], json.dumps(item.get("manifest") or {}, separators=(",", ":"), sort_keys=True), item.get("error") or "",
            ),
        )
        db.commit()
    finally:
        db.close()


def ingest_patch(source: Path, *, remove_source: bool = True, trusted_root: bool = False) -> dict[str, Any]:
    source = source.expanduser().resolve()
    details = inspect_patch(source)
    digest = sha256_file(source)
    if _already_ingested(digest):
        raise IntakeError("byte-identical patch is already queued/applied/reviewed")

    intake_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}"
    legacy_policy = str((load_settings().get("security", {}) or {}).get("legacyPatchPolicy") or "review").strip().casefold()
    if not bool(details.get("modern")) and not trusted_root and legacy_policy == "review":
        project = str(details.get("project") or "unassigned")
        receipt = archive_artifact_file(
            source, project, category="review", move=remove_source,
            metadata={
                "artifactType": "legacy-patch",
                "verificationClass": details.get("verificationClass"),
                "packageCreatedUtc": details.get("packageCreatedUtc", ""),
                "dateStatus": details.get("dateStatus", ""),
                "reason": "Legacy/unbound patch discovered outside a trusted project root; retained for review rather than auto-queued.",
            },
        )
        item = {
            "schema": "vault.intake.receipt.v1", "version": VAULT_INTAKE_VERSION,
            "intake_id": intake_id, "source_name": source.name, "original_path": str(source),
            "sha256": digest, "bytes": int(receipt.get("bytes", 0) or 0),
            "classification": "PATCH-LEGACY-REVIEW", "state": "REVIEW",
            "target_project": project, "patch_id": details["patchId"], "received_utc": utc_now(),
            "vault_path": str(receipt.get("artifactPath") or ""), "manifest": details["manifest"],
            "package_created_utc": details.get("packageCreatedUtc", ""), "date_status": details.get("dateStatus", ""),
            "verification_class": details.get("verificationClass", "LEGACY-UNBOUND"),
            "legacy_patch_id": bool(details.get("legacyPatchId")), "source_mtime_utc": "", "error": "",
        }
        _persist_item(item); _write_receipt(item)
        return item

    intake_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}"
    quarantine = vault_root() / "intake" / "quarantine" / intake_id
    quarantine.mkdir(parents=True, exist_ok=True)
    staged = quarantine / source.name
    temp = quarantine / (source.name + ".copying")
    shutil.copy2(source, temp)
    copied_digest = sha256_file(temp)
    if copied_digest != digest:
        temp.unlink(missing_ok=True)
        raise IntakeError("Vault quarantine copy hash mismatch")
    os.replace(temp, staged)

    project = details["project"] or "unassigned"
    safe_project = re.sub(r"[^A-Za-z0-9._-]+", "-", project).strip("-") or "unassigned"
    safe_patch = re.sub(r"[^A-Za-z0-9._-]+", "-", details["patchId"]).strip("-") or intake_id
    artifact_tree = ensure_artifact_project_tree(safe_project)
    # Global intake (Downloads, watched folders) is catalog-only.  A downloaded patch
    # must never become an executable update merely because it matches a registered
    # project.  Only a deliberate trusted-root drop is QUEUED automatically.
    intake_bucket = "queued" if trusted_root else "available"
    intake_state = "QUEUED" if trusted_root else "AVAILABLE"
    intake_classification = "PATCH" if trusted_root else "PATCH-AVAILABLE"
    package_dir = artifact_tree["patches"] / intake_bucket / safe_patch
    package_dir.mkdir(parents=True, exist_ok=True)
    stored = package_dir / source.name
    if stored.exists():
        stored = package_dir / f"{intake_id}_{source.name}"
    _promote_verified(staged, stored, digest, remove_source=True)
    # Preserve durable transport evidence beside the package regardless of whether
    # it is only AVAILABLE or deliberately QUEUED.
    Path(str(stored) + ".sha256").write_text(f"{digest}  {stored.name}\n", encoding="ascii")
    (package_dir / "manifest.json").write_text(json.dumps(details["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        quarantine.rmdir()
    except OSError:
        pass

    item = {
        "schema": "vault.intake.receipt.v1",
        "version": VAULT_INTAKE_VERSION,
        "intake_id": intake_id,
        "source_name": source.name,
        "original_path": str(source),
        "sha256": digest,
        "bytes": source.stat().st_size,
        "classification": intake_classification,
        "state": intake_state,
        "target_project": project,
        "patch_id": details["patchId"],
        "received_utc": utc_now(),
        "vault_path": str(stored),
        "manifest": details["manifest"],
        "package_created_utc": details.get("packageCreatedUtc", ""),
        "date_status": details.get("dateStatus", ""),
        "legacy_patch_id": bool(details.get("legacyPatchId")),
        "verification_class": details.get("verificationClass", ""),
        "build_bound": bool(details.get("buildBound")),
        "source_mtime_utc": datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc).isoformat(),
        "error": "",
    }
    _persist_item(item)
    _write_receipt(item)

    # Never remove the browser/download copy until the Vault copy is durable and hash-verified.
    if remove_source:
        source.unlink()
        for suffix in (".sha256", ".sha256.txt"):
            sidecar = Path(str(source) + suffix)
            if sidecar.is_file():
                sidecar.unlink()
    return item


def _archive_global_rejected_transport(path: Path, *, reason: str, remove_source: bool) -> dict[str, Any] | None:
    """Move a rejected global patch candidate to Artifact Central review without executing it.

    This intentionally does not parse/extract the transport again.  Even an oversized or
    malformed ZIP can be retained as inert evidence.  Project attribution is conservative
    and uses only the registered-project filename matcher; otherwise the item is unassigned.
    """
    if not remove_source or not path.is_file():
        return None
    project = identify_project(path) or "unassigned"
    try:
        receipt = archive_artifact_file(
            path,
            project,
            category="review",
            move=True,
            metadata={
                "artifactType": "rejected-patch-transport",
                "intakeDisposition": "REVIEW-NONEXECUTABLE",
                "reason": str(reason),
                "sourceMtimeUtc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
                "intakeUtc": utc_now(),
            },
        )
    except Exception:
        return None
    digest = str(receipt.get("sha256") or "")
    intake_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}"
    item = {
        "schema": "vault.intake.receipt.v1",
        "version": VAULT_INTAKE_VERSION,
        "intake_id": intake_id,
        "source_name": path.name,
        "original_path": str(path),
        "sha256": digest,
        "bytes": int(receipt.get("bytes", 0) or 0),
        "classification": "PATCH-REJECTED-REVIEW",
        "state": "REVIEW",
        "target_project": project,
        "patch_id": f"review-{digest[:12]}" if digest else f"review-{uuid.uuid4().hex[:12]}",
        "received_utc": utc_now(),
        "vault_path": str(receipt.get("artifactPath") or ""),
        "manifest": {},
        "error": str(reason),
    }
    try:
        _persist_item(item)
        _write_receipt(item)
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
            is_named_patch = path.suffix.casefold() == ".zip" and bool(PATCH_NAME_RE.search(path.name)) and not bool(NON_PATCH_RE.search(path.name))
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
                    if not force_stable and (age < stable_seconds or stable_count < 2):
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
                if not force_stable and (age < stable_seconds or stable_count < 2):
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
    # Compatibility wrapper used by older Forge/PCC surfaces.
    return scan_roots(downloads_roots(), force_stable=force_stable, remove_source=remove_source)


def scan_intake(*, extra_roots: Sequence[Path] = (), force_stable: bool = False, remove_source: bool = True) -> dict[str, Any]:
    return scan_roots(intake_roots(extra_roots), force_stable=force_stable, remove_source=remove_source, trusted_roots=extra_roots)

def list_items(*, state: str | None = None, project: str | None = None) -> list[dict[str, Any]]:
    db = _connect()
    try:
        sql = "SELECT intake_id,source_name,original_path,sha256,bytes,classification,state,target_project,patch_id,received_utc,vault_path,manifest_json,error FROM intake_items"
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
        keys = ["intake_id","source_name","original_path","sha256","bytes","classification","state","target_project","patch_id","received_utc","vault_path","manifest_json","error"]
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


def counts_for_project(*names: str) -> tuple[int, int]:
    wanted = {name.strip().casefold() for name in names if name and name.strip()}
    db = _connect()
    try:
        rows = db.execute("SELECT target_project,state,error,original_path FROM intake_items WHERE state IN ('QUEUED','STAGED','REJECTED','FAILED')").fetchall()
    finally:
        db.close()
    pending = invalid = 0
    for project, state, error, original_path in rows:
        project_key = str(project or "").casefold()
        # Downloads is catalog-only. Legacy rows created before F60R1 must never show up
        # as executable pending work, even if an older scanner assigned a project name.
        if str(state).upper() in {"QUEUED", "STAGED"} and _origin_is_global_download(str(original_path or "")):
            continue
        # A global/unassigned legacy queue entry is not an update for every project.
        # Only an explicit target alias may contribute to this project's pending/invalid counts.
        if wanted and project_key not in wanted:
            continue
        if str(state).upper() in {"QUEUED", "STAGED"}:
            pending += 1
        else:
            invalid += 1
    return pending, invalid


def _project_aliases(root: Path) -> set[str]:
    aliases = {root.name.casefold()}
    try:
        from PCCProjectDiscovery import discover_project_contract_data
        data = discover_project_contract_data(root)
        project = data.get("project") or {}
        for value in (project.get("id"), project.get("name")):
            if value:
                aliases.add(str(value).strip().casefold())
    except Exception:
        pass
    if "forge-project-control-center" in aliases or (root / "app" / "ForgeVersion.py").is_file():
        aliases.update({"forge", "vault", "vault-project-control-center"})
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


def stage_for_project(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    aliases = _project_aliases(root)
    items = [item for item in list_items() if item.get("state") in {"QUEUED", "STAGED"}]

    # F60R2 migration guard: older releases could queue Downloads entries. Downloads is
    # now catalog-only, so demote any such legacy rows before an operation can stage/apply them.
    for item in items:
        if str(item.get("target_project") or "").casefold() not in aliases:
            continue
        if not _origin_is_global_download(str(item.get("original_path") or "")):
            continue
        if str(item.get("state") or "").upper() == "STAGED":
            staged_copy = root / "updates" / "inbox" / str(item.get("source_name") or "")
            try:
                if staged_copy.is_file() and sha256_file(staged_copy) == str(item.get("sha256") or ""):
                    staged_copy.unlink(missing_ok=True)
                    Path(str(staged_copy) + ".sha256").unlink(missing_ok=True)
            except OSError:
                pass
        _set_item_state(str(item.get("intake_id") or ""), "AVAILABLE", error="legacy Downloads queue demoted to catalog-only by Forge F60R2")

    items = [item for item in list_items() if item.get("state") in {"QUEUED", "STAGED"}]
    selected = [item for item in items if str(item.get("target_project") or "").casefold() in aliases]
    if not selected:
        return {"staged": 0, "items": [], "root": str(root)}
    inbox = root / "updates" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    staged_rows: list[dict[str, Any]] = []
    for item in selected:
        source = Path(str(item["vault_path"]))
        if not source.is_file():
            _set_item_state(str(item["intake_id"]), "FAILED", error="queued Vault transport missing")
            raise IntakeError(f"queued Vault transport missing: {source}")
        expected = str(item["sha256"])
        manifest = item.get("manifest") if isinstance(item.get("manifest"), dict) else {}
        verification = verify_manifest_preconditions(manifest, root)
        if verification.get("status") != "PASS":
            detail = "; ".join(f"{x.get('field')}: expected {x.get('expected')} actual {x.get('actual') or '<missing>'}" for x in verification.get("mismatches", []))
            _set_item_state(str(item["intake_id"]), "FAILED", error="build identity mismatch: " + detail)
            raise IntakeError("patch does not match active project/build identity: " + detail)
        if sha256_file(source) != expected:
            _set_item_state(str(item["intake_id"]), "FAILED", error="queued Vault transport hash mismatch")
            raise IntakeError(f"queued Vault transport hash mismatch: {source}")
        dest = inbox / source.name
        if dest.exists():
            if sha256_file(dest) != expected:
                raise IntakeError(f"project inbox already contains conflicting transport: {dest.name}")
        else:
            temp = inbox / (source.name + ".vault-copying")
            shutil.copy2(source, temp)
            if sha256_file(temp) != expected:
                temp.unlink(missing_ok=True)
                raise IntakeError(f"project inbox copy hash mismatch: {source.name}")
            os.replace(temp, dest)
        Path(str(dest) + ".sha256").write_text(f"{expected}  {dest.name}\n", encoding="ascii")
        _set_item_state(str(item["intake_id"]), "STAGED")
        staged_rows.append({"patchId": item["patch_id"], "source": str(source), "projectInbox": str(dest), "buildVerification": verification})
    return {"staged": len(staged_rows), "items": staged_rows, "root": str(root)}


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
                print(f"[PASS] QUEUED {item['patch_id']} -> {item['vault_path']}", flush=True)
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
