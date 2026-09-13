#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from ForgeRuntimeCompatibility import install_import_compatibility

install_import_compatibility()

import VaultIntake as _impl
from VaultIntake import *  # noqa: F401,F403

INTAKE_FACADE_VERSION = "FORGEPY-INTAKE-FACADE-F754"

_ORIGINAL_RESOLVE_PATCH_TARGET = _impl.resolve_patch_target


def parse_canonical_patch_filename(path: Path | str) -> dict[str, str]:
    source = Path(path)
    match = _impl.CANONICAL_PATCH_FILE_RE.fullmatch(source.name)
    if match is None:
        stem = re.sub(r"\s+\(\d+\)$", "", source.stem)
        match = _impl.CANONICAL_PATCH_FILE_RE.fullmatch(stem + source.suffix)
    if match is None:
        return {}
    out = {key: str(value) for key, value in match.groupdict().items()}
    try:
        datetime.strptime(out["date"], "%Y%m%d")
    except ValueError:
        return {}
    return out


_impl.parse_canonical_patch_filename = parse_canonical_patch_filename


def _identity_forms(value: str) -> set[str]:
    helper = getattr(_impl, "_project_identity_forms", None)
    if callable(helper):
        return set(helper(value))
    raw = str(value or "").strip().casefold()
    return {raw, re.sub(r"[^a-z0-9]+", "", raw)} if raw else set()


def _registered_entries() -> list[Any]:
    helper = getattr(_impl, "_registered_project_entries", None)
    return list(helper() if callable(helper) else [])


def _cheap_declared_entry(declared: str) -> Any | None:
    wanted = _identity_forms(declared)
    hits = []
    for entry in _registered_entries():
        root = Path(entry.root).expanduser().resolve()
        forms = set()
        for value in (getattr(entry, "project_id", ""), getattr(entry, "name", ""), root.name):
            forms.update(_identity_forms(str(value or "")))
        if wanted & forms:
            hits.append(entry)
    return hits[0] if len(hits) == 1 else None




def _git_binary() -> str:
    try:
        from ForgeStatusCache import git_binary
        return git_binary()
    except Exception:
        import shutil
        return shutil.which("git") or ""

def _git_apply_probe(source: Path, root: Path, timeout_seconds: float = 6.0) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not (root / ".git").exists():
        return {
            "status": "FAIL",
            "identity": {},
            "matched": [],
            "mismatches": [{"field": "gitApplyCheck", "expected": "clean apply", "actual": "not a Git working tree"}],
            "declared": {"gitApplyCheck": True},
        }
    git = _git_binary()
    if not git:
        return {
            "status": "FAIL", "identity": {}, "matched": [],
            "mismatches": [{"field": "gitApplyCheck", "expected": "clean apply", "actual": "Git executable unavailable"}],
            "declared": {"gitApplyCheck": True},
        }
    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
        startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
    try:
        cp = subprocess.run(
            [git, "-C", str(root), "apply", "--check", "--whitespace=nowarn", str(source)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            creationflags=flags,
            startupinfo=startupinfo,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "FAIL",
            "identity": {},
            "matched": [],
            "mismatches": [{"field": "gitApplyCheck", "expected": "clean apply", "actual": f"routing probe timed out after {timeout_seconds:g}s"}],
            "declared": {"gitApplyCheck": True},
        }
    if cp.returncode == 0:
        return {
            "status": "PASS",
            "identity": {},
            "matched": [{"field": "gitApplyCheck", "expected": "clean apply", "actual": "PASS"}],
            "mismatches": [],
            "declared": {"gitApplyCheck": True},
            "transportVerification": {"routingProbe": "git apply --check", "timeoutSeconds": timeout_seconds},
        }
    detail = (cp.stderr or cp.stdout or "git apply --check failed").strip()
    return {
        "status": "FAIL",
        "identity": {},
        "matched": [],
        "mismatches": [{"field": "gitApplyCheck", "expected": "clean apply", "actual": detail}],
        "declared": {"gitApplyCheck": True},
    }


def _row(entry: Any, verification: dict[str, Any]) -> dict[str, Any]:
    root = Path(entry.root).expanduser().resolve()
    return {
        "projectId": str(getattr(entry, "project_id", "") or root.name),
        "name": str(getattr(entry, "name", "") or root.name),
        "root": str(root),
        "status": str(verification.get("status") or "FAIL"),
        "verification": verification,
    }


def _declared_from_details(source: Path, details: dict[str, Any]) -> tuple[str, bool, dict[str, Any]]:
    manifest = details.get("manifest") if isinstance(details.get("manifest"), dict) else {}
    schema = str(manifest.get("schema") or details.get("schema") or "").casefold()
    unified = schema == "forge.patch.unified-diff.v1" or str(details.get("transportFormat") or "").casefold() == "unified-diff"
    if unified:
        filename_meta = details.get("filenameMeta") if isinstance(details.get("filenameMeta"), dict) else parse_canonical_patch_filename(source)
        declared = str((filename_meta or {}).get("project") or "unassigned").strip()
    else:
        declared = str(
            details.get("project")
            or manifest.get("project")
            or manifest.get("projectId")
            or manifest.get("targetProject")
            or "unassigned"
        ).strip()
    return declared, unified, manifest


def resolve_patch_target(source: Path, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        return _ORIGINAL_RESOLVE_PATCH_TARGET(source, details=details)

    try:
        resolved_details = dict(details or _impl.inspect_patch(source, project_hint=None))
    except Exception:
        return _ORIGINAL_RESOLVE_PATCH_TARGET(source, details=details)

    declared, unified, manifest = _declared_from_details(source, resolved_details)

    if declared and declared.casefold() != "unassigned":
        entry = _cheap_declared_entry(declared)
        if entry is not None:
            root = Path(entry.root).expanduser().resolve()
            verification = _git_apply_probe(source, root) if unified else getattr(_impl, "_verify_transport_for_root")(manifest, source, root)
            row = _row(entry, verification)
            if row["status"] == "PASS":
                return {
                    "status": "RESOLVED",
                    "declaredProject": declared,
                    "targetRoot": row["root"],
                    "targetProject": row["projectId"],
                    "targetName": row["name"],
                    "matches": [row],
                    "checks": [row],
                    "details": resolved_details,
                    "reason": "declared project resolved through registry fast path",
                    "routing": "FORGEPY-F452-FAST",
                }
            if not unified:
                try:
                    from ForgePYPatchEngine import target_satisfaction
                    target_state = dict(target_satisfaction(source, root) or {})
                except Exception as exc:
                    target_state = {"status": "UNKNOWN", "reason": str(exc)}
                if str(target_state.get("status") or "").upper() == "ALREADY_TARGET":
                    return {
                        "status": "ALREADY_TARGET",
                        "declaredProject": declared,
                        "targetRoot": row["root"],
                        "targetProject": row["projectId"],
                        "targetName": row["name"],
                        "matches": [row],
                        "checks": [row],
                        "details": resolved_details,
                        "targetSatisfaction": target_state,
                        "reason": "patch target is already fully installed; no source changes are required",
                        "routing": "FORGEPY-F754-ALREADY-TARGET",
                    }
            # Do not weaken the Forge universal engine. If the project itself exposes
            # transactional patch + recovery authority, an explicit manual selection may
            # instead be handed to that internal PCC for its own compatibility decision.
            # This is REVIEW routing, not a Forge compatibility claim.
            try:
                from ForgeProjectPCC import profile as pcc_profile
                native = pcc_profile(root)
            except Exception:
                native = {}
            if not unified and bool(native.get("nativePatchReady")):
                return {
                    "status": "PROJECT_NATIVE_REVIEW",
                    "declaredProject": declared,
                    "targetRoot": row["root"],
                    "targetProject": row["projectId"],
                    "targetName": row["name"],
                    "matches": [row],
                    "checks": [row],
                    "details": resolved_details,
                    "reason": "Forge build/source preconditions are not satisfied, but the registered project exposes internal PCC patch + recovery authority; exact transport can be delegated for project-native review",
                    "routing": "FORGEPY-F797-PROJECT-NATIVE",
                }
            return {
                "status": "INCOMPATIBLE",
                "declaredProject": declared,
                "targetRoot": "",
                "targetProject": "",
                "targetName": "",
                "matches": [],
                "checks": [row],
                "details": resolved_details,
                "reason": "declared project is registered, but the patch does not apply to its current source/build",
                "routing": "FORGEPY-F452-FAST",
            }
        return _ORIGINAL_RESOLVE_PATCH_TARGET(source, details=resolved_details)

    if not unified:
        return _ORIGINAL_RESOLVE_PATCH_TARGET(source, details=resolved_details)

    entries = _registered_entries()
    checks = []
    matches = []

    def check(entry: Any) -> dict[str, Any]:
        root = Path(entry.root).expanduser().resolve()
        return _row(entry, _git_apply_probe(source, root))

    if entries:
        with ThreadPoolExecutor(max_workers=min(4, len(entries)), thread_name_prefix="ForgePatchRoute") as pool:
            future_map = {pool.submit(check, entry): entry for entry in entries}
            for future in as_completed(future_map):
                try:
                    row = future.result()
                except Exception as exc:
                    row = _row(
                        future_map[future],
                        {
                            "status": "FAIL",
                            "identity": {},
                            "matched": [],
                            "mismatches": [{"field": "routingProbe", "expected": "completed", "actual": str(exc)}],
                            "declared": {},
                        },
                    )
                checks.append(row)
                if row["status"] == "PASS":
                    matches.append(row)

    if len(matches) == 1:
        hit = matches[0]
        return {
            "status": "RESOLVED",
            "declaredProject": declared,
            "targetRoot": hit["root"],
            "targetProject": hit["projectId"],
            "targetName": hit["name"],
            "matches": matches,
            "checks": checks,
            "details": resolved_details,
            "reason": "exactly one registered project passed the bounded Git applicability probe",
            "routing": "FORGEPY-F453-PARALLEL",
        }

    if len(matches) > 1:
        names = ", ".join(f"{row['name']} ({row['root']})" for row in matches)
        return {
            "status": "AMBIGUOUS",
            "declaredProject": declared,
            "targetRoot": "",
            "targetProject": "",
            "targetName": "",
            "matches": matches,
            "checks": checks,
            "details": resolved_details,
            "reason": "patch is compatible with more than one registered project: " + names,
            "routing": "FORGEPY-F453-PARALLEL",
        }

    return {
        "status": "INCOMPATIBLE",
        "declaredProject": declared,
        "targetRoot": "",
        "targetProject": "",
        "targetName": "",
        "matches": [],
        "checks": checks,
        "details": resolved_details,
        "reason": "patch does not currently apply to any registered Git project",
        "routing": "FORGEPY-F453-PARALLEL",
    }


_impl.resolve_patch_target = resolve_patch_target


def queue_patch_to_project(root: Path, source: Path) -> dict[str, Any]:
    """Explicitly validate and queue a selected patch for one project.

    Queueing never modifies project source. The Project Dashboard / explicit
    patch-apply operation is the adoption boundary.
    """
    root = Path(root).expanduser().resolve()
    source = Path(source).expanduser().resolve()
    approved = _impl.approve_manual_patch_for_project(root, source)
    out = dict(approved or {})
    out.setdefault("state", "QUEUED")
    out["queuedOnly"] = True
    out["targetRoot"] = str(root)
    return out


def queue_manual_patch(source: Path) -> dict[str, Any]:
    """Resolve a selected patch globally, then queue it to exactly one project."""
    source = Path(source).expanduser().resolve()
    resolution = dict(resolve_patch_target(source) or {})
    if str(resolution.get("status") or "").upper() != "RESOLVED":
        return {
            "status": str(resolution.get("status") or "INCOMPATIBLE"),
            "queued": False,
            "resolution": resolution,
        }
    root = Path(str(resolution.get("targetRoot") or "")).expanduser().resolve()
    queued = queue_patch_to_project(root, source)
    return {
        "status": "QUEUED",
        "queued": True,
        "targetRoot": str(root),
        "targetProject": resolution.get("targetProject") or root.name,
        "resolution": resolution,
        "queue": queued,
    }


def stage_project_native_patch(root: Path, source: Path) -> dict[str, Any]:
    """Bridge exact bytes to a project-owned PCC without converting the patch schema."""
    from ForgeProjectPCC import stage_exact_transport
    return stage_exact_transport(Path(root), Path(source))


def retain_already_applied_patch(source: Path, resolution: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retain an explicitly selected, already-installed transport as inert lineage."""
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        return {"state": "LINEAGE", "classification": "PATCH-LINEAGE-ALREADY-APPLIED", "stored": "", "sourceMissing": True}
    resolution = dict(resolution or {})
    details = resolution.get("details") if isinstance(resolution.get("details"), dict) else {}
    if not details:
        details = dict(_impl.inspect_patch(source, project_hint=None))
    archived = _impl._archive_lineage_transport(
        source, details, relation="already-applied", remove_source=True,
        reason="selected transport target is already fully installed",
    )
    item = _impl._lineage_item(source, details, archived, error="patch already applied; target payload already satisfied")
    item["classification"] = "PATCH-LINEAGE-ALREADY-APPLIED"
    item["relationship"] = "already-applied"
    _impl._persist_item(item)
    _impl._write_receipt(item)
    return item
