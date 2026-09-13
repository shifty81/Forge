#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from ForgeInstallLayout import ensure, resolve

MAINT_VERSION = "FORGEPY-SELF-MAINTENANCE-2.0-F740"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def layout(app_root: Path | None = None, mode: str | None = None) -> dict[str, Any]:
    return ensure(resolve(app_root, mode))


def _maintenance_root(current_root: Path, mode: str | None = None) -> Path:
    """Keep staging/rollback outside the application image being replaced."""
    current_root = current_root.expanduser().resolve()
    lay = resolve(current_root, mode)
    if str(lay.get("mode") or "").casefold() == "portable":
        return current_root.parent / f".{current_root.name}.ForgePYMaintenance"
    return Path(lay["updatesRoot"]).parent / "ApplicationMaintenance"


def _safe_extract_bundle(bundle: Path, destination: Path) -> dict[str, Any]:
    with zipfile.ZipFile(bundle, "r") as archive:
        try:
            manifest = json.loads(archive.read("FORGEPY_UPDATE_MANIFEST.json").decode("utf-8"))
        except KeyError as exc:
            raise RuntimeError("ForgePY application update bundle is missing FORGEPY_UPDATE_MANIFEST.json") from exc
        if str(manifest.get("schema") or "") != "forgepy.application-update.v1":
            raise RuntimeError("unsupported ForgePY application update schema")

        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        for member in archive.infolist():
            name = member.filename.replace("\\", "/")
            if not name.startswith("image/") or name.endswith("/"):
                continue
            rel = name[len("image/"):]
            target = (destination / rel).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise RuntimeError(f"unsafe update-bundle path: {name}") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)

    expected = manifest.get("files") or []
    for row in expected:
        rel = str(row.get("path") or "")
        target = destination / rel
        if not target.is_file():
            raise RuntimeError(f"application update missing file: {rel}")
        expected_hash = str(row.get("sha256") or "").casefold()
        if expected_hash and _sha(target).casefold() != expected_hash:
            raise RuntimeError(f"application update hash mismatch: {rel}")

    if not (destination / "ForgePY.exe").is_file():
        raise RuntimeError("application update does not contain ForgePY.exe")
    return manifest


def queue_update(source: Path, app_root: Path | None = None, mode: str | None = None) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    lay = layout(app_root, mode)
    incoming = Path(lay["updatesRoot"]) / "Incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    target = incoming / f"{uuid.uuid4().hex[:8]}__{source.name}"
    shutil.copy2(source, target)
    kind = "application-image" if source.suffix.casefold() == ".forgeupdate" else "source-transport"
    row = {
        "id": target.stem,
        "source": str(target),
        "original": str(source),
        "sha256": _sha(target),
        "state": "QUEUED",
        "kind": kind,
    }
    target.with_suffix(target.suffix + ".json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return row


def items(app_root: Path | None = None, mode: str | None = None) -> list[dict[str, Any]]:
    lay = layout(app_root, mode)
    incoming = Path(lay["updatesRoot"]) / "Incoming"
    rows: list[dict[str, Any]] = []
    for meta in sorted(incoming.glob("*.json")) if incoming.exists() else []:
        try:
            row = json.loads(meta.read_text(encoding="utf-8"))
            if isinstance(row, dict):
                row["_metadataPath"] = str(meta)
                rows.append(row)
        except Exception:
            pass
    return rows


def queued(app_root: Path | None = None, mode: str | None = None) -> list[dict[str, Any]]:
    return [row for row in items(app_root, mode) if str(row.get("state") or "").upper() == "QUEUED"]

def _prepare_application_bundle(transport: Path, current_root: Path, mode: str | None) -> dict[str, Any]:
    maint = _maintenance_root(current_root, mode)
    staged_parent = maint / "Staged"
    staged_parent.mkdir(parents=True, exist_ok=True)
    staged = staged_parent / f"ForgePY-next-{uuid.uuid4().hex[:8]}"
    manifest = _safe_extract_bundle(transport, staged)
    return {
        "schema": "forgepy.self-update-stage.v2",
        "version": MAINT_VERSION,
        "state": "STAGED",
        "kind": "application-image",
        "transport": str(transport),
        "transportSha256": _sha(transport),
        "currentRoot": str(current_root),
        "stagedRoot": str(staged),
        "applicationVersion": str(manifest.get("applicationVersion") or ""),
        "applicationBuild": str(manifest.get("applicationBuild") or ""),
    }


def _prepare_source_transport(transport: Path, current_root: Path, mode: str | None) -> dict[str, Any]:
    # Development/source-mode only. A compiled onedir image cannot consume Python
    # source patches because its modules are compiled into the executable image.
    if not (current_root / "app" / "ForgePYBootstrap.py").is_file():
        raise RuntimeError(
            "This installed ForgePY build requires a .forgeupdate application bundle. "
            "Source .patch/.zip transports are supported only from a ForgePY source checkout."
        )

    maint = _maintenance_root(current_root, mode)
    staged_parent = maint / "Staged"
    staged_parent.mkdir(parents=True, exist_ok=True)
    staged = staged_parent / f"ForgePY-source-next-{uuid.uuid4().hex[:8]}"
    ignore = shutil.ignore_patterns(
        "Data", "Logs", "Cache", "Updates", "Rollback",
        "dist", "build", "builds", "__pycache__", "*.pyc",
    )
    shutil.copytree(current_root, staged, ignore=ignore)
    try:
        from ForgePYPatchEngine import can_apply_transport, apply_transport
        if not can_apply_transport(transport):
            raise RuntimeError("transport is not supported by the canonical ForgePY patch engine")
        receipt = apply_transport(transport, staged)
    except Exception:
        shutil.rmtree(staged, ignore_errors=True)
        raise
    return {
        "schema": "forgepy.self-update-stage.v2",
        "version": MAINT_VERSION,
        "state": "STAGED",
        "kind": "source-transport",
        "transport": str(transport),
        "transportSha256": _sha(transport),
        "currentRoot": str(current_root),
        "stagedRoot": str(staged),
        "receipt": receipt,
        "requiresExecutableRebuild": True,
    }


def prepare_patch(
    transport: Path,
    current_root: Path,
    *,
    approved: bool = False,
    mode: str | None = None,
) -> dict[str, Any]:
    if not approved:
        raise PermissionError("ForgePY self-update staging requires explicit approval")
    current_root = current_root.expanduser().resolve()
    transport = transport.expanduser().resolve()
    if not transport.is_file():
        raise FileNotFoundError(transport)

    if transport.suffix.casefold() == ".forgeupdate":
        plan = _prepare_application_bundle(transport, current_root, mode)
    else:
        plan = _prepare_source_transport(transport, current_root, mode)

    maint = _maintenance_root(current_root, mode)
    maint.mkdir(parents=True, exist_ok=True)
    (maint / "current-plan.json").write_text(json.dumps(plan, indent=2, default=str) + "\n", encoding="utf-8")
    return plan


def _rollback_root(current: Path, mode: str | None) -> Path:
    maint = _maintenance_root(current, mode)
    path = maint / "Rollback" / "ForgePY.previous"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def promotion_powershell(plan: dict[str, Any], exe_name: str = "ForgePY.exe", mode: str | None = None) -> Path:
    current = Path(plan["currentRoot"]).expanduser().resolve()
    staged = Path(plan["stagedRoot"]).expanduser().resolve()
    lay = resolve(current, mode)
    portable = str(lay.get("mode") or "").casefold() == "portable"
    rollback = _rollback_root(current, mode)

    helpers = Path(tempfile.gettempdir()) / "ForgePY-UpdateHelpers"
    helpers.mkdir(parents=True, exist_ok=True)
    script = helpers / f"Promote-ForgePY-{uuid.uuid4().hex[:8]}.ps1"

    q = lambda value: "'" + str(value).replace("'", "''") + "'"
    lines = [
        "param([int]$PidToWait)",
        '$ErrorActionPreference = "Stop"',
        "while (Get-Process -Id $PidToWait -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 250 }",
        f"$current = {q(current)}",
        f"$staged = {q(staged)}",
        f"$rollback = {q(rollback)}",
        "$currentParent = Split-Path -Parent $current",
        "New-Item -ItemType Directory -Force -Path (Split-Path -Parent $rollback) | Out-Null",
        "if (Test-Path $rollback) { Remove-Item -Recurse -Force $rollback }",
        "try {",
        "  if (Test-Path $current) { Move-Item -Force $current $rollback }",
        "  Move-Item -Force $staged $current",
    ]
    if portable:
        lines.extend([
            "  $oldData = Join-Path $rollback 'Data'",
            "  $newData = Join-Path $current 'Data'",
            "  if ((Test-Path $oldData) -and -not (Test-Path $newData)) { Move-Item -Force $oldData $newData }",
            "  if (-not (Test-Path (Join-Path $current '.forgepy-portable'))) {",
            "    Set-Content -Path (Join-Path $current '.forgepy-portable') -Value 'ForgePY portable install' -Encoding UTF8",
            "  }",
        ])
    lines.extend([
        f"  Start-Process (Join-Path $current {q(exe_name)})",
        "} catch {",
        "  if ((Test-Path $rollback) -and -not (Test-Path $current)) { Move-Item -Force $rollback $current }",
        "  throw",
        "}",
        "",
    ])
    script.write_text("\n".join(lines), encoding="utf-8")
    return script


def launch_promotion(
    plan: dict[str, Any],
    *,
    approved: bool = False,
    pid_to_wait: int | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    if not approved:
        raise PermissionError("ForgePY promotion requires explicit approval")
    if Path(sys.executable).name.casefold() != "forgepy.exe":
        raise RuntimeError("automatic application-image promotion is enabled only from packaged ForgePY.exe")
    script = promotion_powershell(plan, mode=mode)
    pid = int(pid_to_wait or os.getpid())
    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", str(script),
            "-PidToWait", str(pid),
        ],
        cwd=str(Path(plan["currentRoot"])),
        creationflags=flags,
        close_fds=True,
    )
    return {"ok": True, "state": "ARMED", "helper": str(script), "pidToWait": pid}


def stage_first_queued(
    app_root: Path | None = None,
    mode: str | None = None,
    *,
    approved: bool = False,
) -> dict[str, Any]:
    rows = queued(app_root, mode)
    if not rows:
        raise RuntimeError("no ForgePY application update is queued")
    row = rows[0]
    source = Path(str(row.get("source") or ""))
    current = Path(resolve(app_root, mode)["appRoot"])
    plan = prepare_patch(source, current, approved=approved, mode=mode)
    meta_path = Path(str(row.get("_metadataPath") or ""))
    if meta_path.is_file():
        row["state"] = "STAGED"
        row["stagedRoot"] = plan.get("stagedRoot")
        row.pop("_metadataPath", None)
        meta_path.write_text(json.dumps(row, indent=2, default=str) + "\n", encoding="utf-8")
    return plan


def current_plan(app_root: Path | None = None, mode: str | None = None) -> dict[str, Any] | None:
    current = Path(resolve(app_root, mode)["appRoot"])
    path = _maintenance_root(current, mode) / "current-plan.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def arm_current_plan(
    app_root: Path | None = None,
    mode: str | None = None,
    *,
    approved: bool = False,
) -> dict[str, Any]:
    plan = current_plan(app_root, mode)
    if not plan:
        raise RuntimeError("no staged ForgePY application update is ready")
    if str(plan.get("kind") or "") != "application-image":
        raise RuntimeError(
            "the staged update is a source transport; rebuild ForgePY.exe before application promotion"
        )
    return launch_promotion(plan, approved=approved, mode=mode)
