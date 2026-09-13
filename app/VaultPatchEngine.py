#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from VaultPaths import vault_root
from ForgeUnifiedDiffPatch import is_unified_diff, validate as validate_unified_diff, apply as apply_unified_diff, synthetic_manifest as unified_manifest
from ForgePackagePolicy import self_update_safe, patch_regenerated, classification as package_path_classification

PATCH_ENGINE_VERSION = "FORGE-PATCH-0.5"
SUPPORTED_SCHEMAS = {
    "vault.patch.v1",
    "forge.patch.v1",
    "pcc.patch.v1",
    "forge.test.patch.v1",  # retained for F01-F10 compatibility tests
}


class PatchError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def restart_marker_path() -> Path:
    return vault_root() / "updates" / "restart-required.json"


def _is_vault_application_root(root: Path, manifest: dict[str, Any]) -> bool:
    target = str(manifest.get("project") or manifest.get("projectId") or manifest.get("project_id") or "").strip().casefold()
    if target in {"vault", "vault-project-control-center", "vault-project-control-centre", "forgepy", "forge-py", "forge", "forge-project-control-center", "forge-project-control-centre"}:
        return (root / "app" / "ForgePYStandalone.py").is_file() or (root / "app" / "ForgeStandalone.py").is_file() or (root / "app" / "VaultStandalone.py").is_file()
    return False


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


_TEXT_PREIMAGE_SUFFIXES = {
    ".py", ".pyw", ".md", ".txt", ".json", ".toml", ".yaml", ".yml",
    ".ini", ".cfg", ".cmd", ".bat", ".ps1", ".psm1", ".psd1", ".vbs",
    ".xml", ".html", ".css", ".js", ".ts", ".rs", ".c", ".cc", ".cpp",
    ".h", ".hpp", ".cmake", ".props", ".targets", ".sln", ".vcxproj",
}


def _normalized_text_sha256(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _hash_matches(path: Path, expected: str) -> bool:
    expected = (expected or "").strip().casefold()
    if not expected or not path.is_file():
        return False
    if sha256_file(path) == expected:
        return True
    if path.suffix.casefold() in _TEXT_PREIMAGE_SUFFIXES:
        try:
            return _normalized_text_sha256(path) == expected
        except OSError:
            return False
    return False


def _row_already_satisfied(target: Path, row: dict[str, Any]) -> bool:
    if row["operation"] == "delete":
        return not target.exists()
    target_sha = str(row.get("sha256") or "").strip().casefold()
    return bool(target_sha and target.is_file() and _hash_matches(target, target_sha))


def _safe_rel(raw: str) -> str:
    value = raw.replace("\\", "/").strip()
    p = PurePosixPath(value)
    if not value or p.is_absolute() or re.match(r"^[A-Za-z]:", value) or any(x in {"", ".", ".."} for x in p.parts):
        raise PatchError(f"unsafe patch path: {raw!r}")
    return "/".join(p.parts)


def _target(root: Path, rel: str) -> Path:
    root = root.resolve()
    target = (root / Path(rel)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise PatchError(f"patch target escapes project root: {rel}") from exc
    return target


def _read_manifest(zf: zipfile.ZipFile) -> dict[str, Any]:
    names = [name.replace("\\", "/") for name in zf.namelist()]
    matches = [name for name in names if name.casefold() == "patch_manifest.json"]
    if len(matches) != 1:
        raise PatchError("patch requires exactly one top-level PATCH_MANIFEST.json")
    if PurePosixPath(matches[0]).parent != PurePosixPath("."):
        raise PatchError("PATCH_MANIFEST.json must be top-level")
    try:
        data = json.loads(zf.read(matches[0]).decode("utf-8-sig"))
    except Exception as exc:
        raise PatchError(f"invalid PATCH_MANIFEST.json: {exc}") from exc
    if not isinstance(data, dict):
        raise PatchError("PATCH_MANIFEST.json must be an object")
    return data


def _payload_name(zf: zipfile.ZipFile, rel: str) -> str:
    names = {name.replace("\\", "/").casefold(): name for name in zf.namelist() if not name.endswith("/")}
    for candidate in (f"payload/{rel}", rel):
        hit = names.get(candidate.casefold())
        if hit:
            return hit
    raise PatchError(f"missing payload for {rel}")


def _normalize_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise PatchError("universal Vault patch requires a non-empty files array")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise PatchError("patch files entries must be objects")
        rel = _safe_rel(str(raw.get("path") or raw.get("target") or ""))
        folded = rel.casefold()
        if folded in seen:
            raise PatchError(f"duplicate patch target: {rel}")
        seen.add(folded)
        op = str(raw.get("operation") or raw.get("op") or "write").strip().casefold()
        if op not in {"write", "replace", "add", "delete", "remove"}:
            raise PatchError(f"unsupported operation {op!r} for {rel}")
        out.append({
            "path": rel,
            "operation": "delete" if op in {"delete", "remove"} else "write",
            "sha256": str(raw.get("sha256") or "").strip().casefold(),
            "bytes": raw.get("bytes"),
            "preSha256": str(raw.get("preSha256") or raw.get("beforeSha256") or raw.get("expectedSha256") or "").strip().casefold(),
            "allowMissing": bool(raw.get("allowMissing", False)),
        })
    return out


def can_apply_transport(path: Path) -> bool:
    if is_unified_diff(path):
        return True
    try:
        with zipfile.ZipFile(path, "r") as zf:
            manifest = _read_manifest(zf)
            schema = str(manifest.get("schema") or "").strip().casefold()
            if schema in SUPPORTED_SCHEMAS:
                _normalize_files(manifest)
                return True
            # Any manifest that explicitly requests the Vault universal engine is accepted.
            engine = str(manifest.get("engine") or manifest.get("patchEngine") or "").strip().casefold()
            if engine in {"vault", "vault-universal", "forge-universal"}:
                _normalize_files(manifest)
                return True
    except Exception:
        return False
    return False


def validate_transport(path: Path, root: Path | None = None) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if is_unified_diff(path):
        manifest = unified_manifest(path, root.name if root is not None else "unassigned")
        if root is None:
            return {"manifest": manifest, "files": manifest.get("files", []), "sha256": sha256_file(path), "format": "unified-diff"}
        checked = validate_unified_diff(path, root)
        return {"manifest": manifest, "files": manifest.get("files", []), "sha256": checked["sha256"], "format": "unified-diff", "verification": checked}
    with zipfile.ZipFile(path, "r") as zf:
        manifest = _read_manifest(zf)
        files = _normalize_files(manifest)
        if root is not None and _is_vault_application_root(root, manifest):
            unsafe=[row["path"] for row in files if not self_update_safe(row["path"])]
            if unsafe:
                first=unsafe[0]
                raise PatchError(
                    "unsafe ForgePY self-update target: " + first +
                    " (" + package_path_classification(first) + ")"
                )
        for row in files:
            rel = row["path"]
            if row["operation"] == "write":
                payload = _payload_name(zf, rel)
                info = zf.getinfo(payload)
                mode = (info.external_attr >> 16) & 0xFFFF
                if mode and (stat.S_ISLNK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode)):
                    raise PatchError(f"non-regular payload: {payload}")
                data = zf.read(payload)
                digest = hashlib.sha256(data).hexdigest()
                if row["sha256"] and digest != row["sha256"]:
                    raise PatchError(f"payload hash mismatch: {rel}")
                if row["bytes"] is not None and int(row["bytes"]) != len(data):
                    raise PatchError(f"payload byte-size mismatch: {rel}")
            if root is not None:
                target = _target(root, rel)
                already_satisfied = _row_already_satisfied(target, row)
                if row["preSha256"] and not already_satisfied:
                    if not target.is_file():
                        raise PatchError(f"preimage required but missing: {rel}")
                    if not _hash_matches(target, row["preSha256"]):
                        # FORGEPY_PACKAGE_MANIFEST.json is deterministic gate output, not source
                        # authority. A local Full Gate may legitimately regenerate it between
                        # patch creation and application. Keep every real source preimage strict,
                        # but never let this one generated authority file strand a self-update.
                        if not (_is_vault_application_root(root, manifest) and patch_regenerated(rel)):
                            raise PatchError(f"preimage hash mismatch: {rel}")
                if row["operation"] == "delete" and not target.exists() and not already_satisfied and not row["allowMissing"]:
                    raise PatchError(f"delete target is missing: {rel}")
    return {"manifest": manifest, "files": files, "sha256": sha256_file(path)}


def _safe_project_name(root: Path, manifest: dict[str, Any]) -> str:
    project = str(manifest.get("project") or manifest.get("projectId") or manifest.get("project_id") or root.name)
    return re.sub(r"[^A-Za-z0-9._-]+", "-", project).strip("-") or root.name



def target_satisfaction(path: Path, root: Path) -> dict[str, Any]:
    """Return whether a manifest-backed transport is already fully materialized.

    This is intentionally target-oriented rather than preimage-oriented.  It lets
    intake distinguish an already-installed cumulative patch from a genuinely
    incompatible patch without weakening normal precondition checks.
    """
    path = path.expanduser().resolve()
    root = root.expanduser().resolve()
    if is_unified_diff(path):
        return {"status": "UNKNOWN", "reason": "unified diffs do not carry authoritative target hashes", "satisfied": 0, "total": 0}
    try:
        checked = validate_transport(path, None)
    except Exception as exc:
        return {"status": "INVALID", "reason": str(exc), "satisfied": 0, "total": 0}
    manifest = checked.get("manifest") if isinstance(checked.get("manifest"), dict) else {}
    rows = checked.get("files") if isinstance(checked.get("files"), list) else []
    satisfied = 0
    unsatisfied: list[str] = []
    for row in rows:
        rel = str(row.get("path") or "")
        try:
            target = _target(root, rel)
            ok = _row_already_satisfied(target, row)
        except Exception:
            ok = False
        if ok:
            satisfied += 1
        else:
            unsatisfied.append(rel)

    target_decl = manifest.get("target") if isinstance(manifest.get("target"), dict) else {}
    try:
        from ForgeProjectIdentity import resolve as resolve_project_identity
        live = resolve_project_identity(root)
    except Exception:
        from VaultBuildIdentity import build_identity
        live = build_identity(root)
    expected_build = str(target_decl.get("projectBuild") or target_decl.get("build") or target_decl.get("buildId") or "").strip()
    expected_version = str(target_decl.get("projectVersion") or target_decl.get("version") or target_decl.get("targetVersion") or "").strip()
    actual_build = str(live.get("projectBuild") or "").strip()
    actual_version = str(live.get("projectVersion") or "").strip()
    identity_match = (not expected_build or actual_build == expected_build) and (not expected_version or actual_version == expected_version)
    all_files = bool(rows) and satisfied == len(rows)
    # A zero-row metadata-only transport may still be recognized by exact target identity.
    fully_satisfied = (all_files and identity_match) or (not rows and identity_match and bool(expected_build or expected_version))
    return {
        "status": "ALREADY_TARGET" if fully_satisfied else "NOT_TARGET",
        "reason": "all target files and declared target identity are already satisfied" if fully_satisfied else "target payload is not fully materialized",
        "satisfied": satisfied,
        "total": len(rows),
        "unsatisfied": unsatisfied[:32],
        "target": target_decl,
        "identity": live,
        "identityMatch": identity_match,
    }

def apply_transport(path: Path, root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    path = path.expanduser().resolve()
    if is_unified_diff(path):
        return apply_unified_diff(path, root)
    checked = validate_transport(path, root)
    manifest = checked["manifest"]
    patch_id = str(manifest.get("patchId") or manifest.get("patch_id") or path.stem).strip()
    txid = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    project = _safe_project_name(root, manifest)
    recovery = vault_root() / "recovery" / project / patch_id / txid
    preimage = recovery / "preimage"
    recovery.mkdir(parents=True, exist_ok=True)
    preimage.mkdir(parents=True, exist_ok=True)

    applied: list[dict[str, Any]] = []
    backups: dict[str, Path] = {}
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for row in checked["files"]:
                rel = row["path"]
                target = _target(root, rel)
                existed = target.exists()
                if _row_already_satisfied(target, row):
                    applied.append({
                        "path": rel,
                        "operation": row["operation"],
                        "existed": existed,
                        "status": "already-satisfied",
                    })
                    continue
                if existed:
                    backup = preimage / Path(rel)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    if target.is_dir():
                        raise PatchError(f"file patch target is a directory: {rel}")
                    shutil.copy2(target, backup)
                    backups[rel] = backup
                elif row["preSha256"]:
                    raise PatchError(f"required preimage missing: {rel}")

                if row["operation"] == "delete":
                    target.unlink(missing_ok=row["allowMissing"])
                else:
                    member = _payload_name(zf, rel)
                    data = zf.read(member)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".vault-", dir=str(target.parent))
                    try:
                        with os.fdopen(fd, "wb") as fh:
                            fh.write(data)
                            fh.flush()
                            os.fsync(fh.fileno())
                        os.replace(tmp_name, target)
                    finally:
                        try:
                            os.unlink(tmp_name)
                        except FileNotFoundError:
                            pass
                    if row["sha256"] and sha256_file(target) != row["sha256"]:
                        raise PatchError(f"post-write verification failed: {rel}")
                applied.append({"path": rel, "operation": row["operation"], "existed": existed, "status": "applied"})

        receipt_dir = root / "artifacts" / "patches" / "receipts"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": "vault.patch.receipt.v1",
            "engineVersion": PATCH_ENGINE_VERSION,
            "patchId": patch_id,
            "title": str(manifest.get("title") or patch_id),
            "project": project,
            "status": "applied",
            "transactionId": txid,
            "transport": str(path),
            "transportSha256": checked["sha256"],
            "appliedUtc": utc_now(),
            "files": applied,
            "recovery": str(recovery),
        }
        receipt_path = receipt_dir / f"{patch_id}.json"
        tmp = receipt_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, receipt_path)
        (recovery / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if _is_vault_application_root(root, manifest):
            marker = restart_marker_path()
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker_payload = {
                "schema": "vault.restart-required.v1",
                "patchId": patch_id,
                "title": str(manifest.get("title") or patch_id),
                "root": str(root),
                "writtenUtc": utc_now(),
            }
            tmp_marker = marker.with_suffix(".json.tmp")
            tmp_marker.write_text(json.dumps(marker_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(tmp_marker, marker)
            receipt["restartRequired"] = True
        return receipt
    except Exception as exc:
        rollback_errors: list[str] = []
        for row in reversed(applied):
            if row.get("status") == "already-satisfied":
                continue
            rel = row["path"]
            target = _target(root, rel)
            backup = backups.get(rel)
            try:
                if backup and backup.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, target)
                elif not row["existed"]:
                    target.unlink(missing_ok=True)
            except Exception as rollback_exc:
                rollback_errors.append(f"{rel}: {rollback_exc}")
        failure = {
            "schema": "vault.patch.failure.v1",
            "engineVersion": PATCH_ENGINE_VERSION,
            "patchId": patch_id,
            "project": project,
            "status": "rolled-back" if not rollback_errors else "rollback-attention",
            "transactionId": txid,
            "failedUtc": utc_now(),
            "error": str(exc),
            "rollbackErrors": rollback_errors,
        }
        (recovery / "failure.json").write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise PatchError(str(exc)) from exc


def apply_inbox(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    inbox = root / "updates" / "inbox"
    if not inbox.is_dir():
        return {"applied": 0, "skipped": 0, "items": []}
    applied: list[dict[str, Any]] = []
    skipped = 0
    transports = sorted({*inbox.glob("*.zip"), *inbox.glob("*.patch")}, key=lambda item: item.name.casefold())
    for path in transports:
        if not can_apply_transport(path):
            skipped += 1
            continue
        receipt = apply_transport(path, root)
        applied.append(receipt)
        # The immutable/original transport remains in the global Vault queue/archive. The
        # project inbox is merely a verified staging copy and can be consumed after success.
        path.unlink(missing_ok=True)
        Path(str(path) + ".sha256").unlink(missing_ok=True)
    return {"applied": len(applied), "skipped": skipped, "items": applied}
