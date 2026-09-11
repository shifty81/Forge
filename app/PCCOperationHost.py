#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from PCCProjectDiscovery import discover_project_contract_data
from PCCRepoHygiene import prepare
from VaultIntake import reconcile_project, scan_roots, scan_downloads, stage_for_project
from VaultPatchEngine import apply_inbox, apply_transport, can_apply_transport
from ForgeGreen import certify_green

VERSION = "FORGE-OPERATION-HOST-0.9"

CLEAN_OPERATIONS = {
    "full", "quick", "fast", "build", "build-release", "patch-apply", "self-test",
    "commit-green", "commit-push-green", "push", "git-pull",
    "debug-bundle", "doctor", "root-hygiene", "root-hygiene-fix",
}
PATCH_APPLY_OPERATIONS = {"full", "quick", "fast", "build", "build-release"}


def _print_hygiene(label: str, root: Path) -> int:
    try:
        result = prepare(root, apply=True)
    except Exception as exc:
        print(f"[FAIL] {label} repository transport hygiene failed: {exc}", flush=True)
        return 1
    moved = int(result.get("moved", 0) or 0)
    if moved:
        print(f"[PASS] {label} repository transport hygiene moved {moved} operational artifact(s).", flush=True)
        for row in result.get("moves", []):
            print(f"  MOVE {Path(row['source']).name} -> {row['destination']}", flush=True)
    else:
        print(f"[PASS] {label} repository transport hygiene clean.", flush=True)
    pending = result.get("pendingPatchTransports") or []
    if pending:
        print(f"[INFO] {len(pending)} pending patch transport(s) preserved for Forge intake.", flush=True)
    return 0


def _run(argv: Sequence[str], root: Path) -> int:
    env = os.environ.copy()
    env["PCC_OPERATION_HOST_ACTIVE"] = "1"
    env["VAULT_OPERATION_HOST_ACTIVE"] = "1"
    env["FORGE_OPERATION_HOST_ACTIVE"] = "1"  # F01-F10 compatibility
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.Popen(list(argv), cwd=str(root), stdin=subprocess.DEVNULL, env=env)
    return int(proc.wait())


def _provider_variant(child: Sequence[str], current_operation: str, replacement: str) -> list[str]:
    argv = list(child)
    for index in range(min(6, len(argv))):
        if argv[index] == current_operation:
            argv[index] = replacement
            return argv
    raise RuntimeError(f"cannot derive provider operation {replacement!r} from child argv")


def _project_has_patch_authority(root: Path) -> bool:
    try:
        data = discover_project_contract_data(root)
    except Exception:
        return False
    keys = {str(item.get("key") or "").casefold() for item in data.get("commands", []) if isinstance(item, dict)}
    return "patch.apply" in keys


def _ingest_root_drop(root: Path) -> int:
    """Promote completed *active-project root* transports before hygiene.

    Downloads is a global asynchronous intake surface and must never make an unrelated
    project's build/gate fail. Only malformed patch transports physically dropped into
    the active project root are blocking for that operation.
    """
    try:
        result = scan_roots((root,), force_stable=True, remove_source=True, trusted_roots=(root,))
    except Exception as exc:
        print(f"[FAIL] Forge active-root intake preflight failed: {exc}", flush=True)
        return 1
    for item in result.get("ingested", []):
        state = str(item.get("state") or "").upper()
        if state == "QUEUED":
            print(f"[PASS] Forge incoming.patch explicitly approved and queued {item.get('patch_id')}.", flush=True)
        elif state == "LINEAGE":
            print(f"[INFO] Forge archived non-canonical root transport {item.get('patch_id')} to Patch Lineage; it was not queued.", flush=True)
        else:
            print(f"[INFO] Forge root intake cataloged {item.get('patch_id')} as {state or 'NONEXECUTABLE'}.", flush=True)
    for item in result.get("skipped", []):
        reason = str(item.get("reason") or "skipped")
        if "already queued/applied" not in reason:
            print(f"[INFO] Forge root-drop skipped {item.get('path')}: {reason}", flush=True)
    for item in result.get("errors", []):
        print(f"[FAIL] Forge active-root patch rejected {item.get('path')}: {item.get('error')}", flush=True)
    return 0 if not result.get("errors") else 1


def _poll_downloads_nonblocking() -> None:
    """Best-effort global Downloads intake. Rejections are review items, never gate failures."""
    try:
        result = scan_downloads(force_stable=False, remove_source=True)
    except Exception as exc:
        print(f"[WARN] Forge Downloads intake scan unavailable: {exc}", flush=True)
        return
    cataloged = len(result.get("ingested") or [])
    rejected = len(result.get("errors") or [])
    if cataloged:
        print(f"[INFO] Forge Downloads intake cataloged {cataloged} patch transport(s); none were queued by discovery.", flush=True)
    if rejected:
        print(f"[WARN] Forge Downloads intake has {rejected} rejected/review transport(s); active project gate continues.", flush=True)


def _universal_apply_staged(root: Path, staged: dict[str, object]) -> tuple[int, int]:
    """Apply verified canonical transports directly from Artifact Central.

    This keeps normal Forge updates out of project updates/inbox.  The compatibility
    inbox is used only when a legacy project-native patch authority is required.
    """
    applied = 0
    skipped = 0
    for row in list(staged.get("items") or []):
        source = Path(str(row.get("source") or ""))
        if not source.is_file() or not can_apply_transport(source):
            skipped += 1
            continue
        try:
            receipt = apply_transport(source, root)
            print(f"[PASS] Forge universal patch engine applied {receipt.get('patchId') or source.name} transactionally from Artifact Central.", flush=True)
            applied += 1
        except Exception as exc:
            print(f"[FAIL] Forge universal patch engine failed and rolled back: {exc}", flush=True)
            return 1, skipped
    return 0, skipped

def _apply_staged_updates(root: Path, operation: str, child: Sequence[str]) -> int:
    try:
        staged = stage_for_project(root, compatibility_inbox=False)
    except Exception as exc:
        print(f"[FAIL] Forge could not validate approved patch queue: {exc}", flush=True)
        return 1
    count = int(staged.get("staged", 0) or 0)
    if count == 0:
        return 0
    print(f"[INFO] Forge validated {count} explicitly approved patch(es) for the next {operation} operation.", flush=True)

    # Canonical Forge/Vault patch schemas apply directly from Artifact Central.
    # Only non-universal legacy transports are bridged into a project-native inbox.
    rc, skipped = _universal_apply_staged(root, staged)
    if rc != 0:
        return rc
    # Reconcile canonical transports before any legacy compatibility staging so
    # a project-native inbox can never see and re-apply a package Forge already applied.
    try:
        reconcile_project(root)
    except Exception as exc:
        print(f"[WARN] Canonical patch applied, but early lineage reconciliation needs attention: {exc}", flush=True)
    if skipped:
        if not _project_has_patch_authority(root):
            print(f"[FAIL] {skipped} approved transport(s) require a project-specific patch authority.", flush=True)
            return 1
        try:
            compat = stage_for_project(root, compatibility_inbox=True)
            apply_child = _provider_variant(child, operation, "patch-apply")
        except Exception as exc:
            print(f"[FAIL] Could not prepare project compatibility patch authority: {exc}", flush=True)
            return 1
        if int(compat.get("staged", 0) or 0) <= 0:
            print("[FAIL] No compatibility transports were staged for the project-native patch authority.", flush=True)
            return 1
        rc = _run(apply_child, root)
        if rc != 0:
            print(f"[FAIL] Project patch authority rejected/failed approved patch(es), exit={rc}.", flush=True)
            return rc

    try:
        reconciled = reconcile_project(root)
        promoted = int(reconciled.get("reconciled", 0) or 0)
        if promoted:
            print(f"[PASS] Forge reconciled {promoted} applied patch(es) into durable Patch Lineage.", flush=True)
    except Exception as exc:
        print(f"[WARN] Patch applied, but Forge lineage reconciliation needs attention: {exc}", flush=True)
    return 0

def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Forge universal operation host")
    ap.add_argument("--root", required=True)
    ap.add_argument("--operation", required=True)
    ap.add_argument("child", nargs=argparse.REMAINDER)
    ns = ap.parse_args(argv)
    root = Path(ns.root).expanduser().resolve()
    operation = str(ns.operation)
    child = list(ns.child)
    if child and child[0] == "--":
        child = child[1:]
    if not child:
        print("[FAIL] Forge operation host received no provider command.", flush=True)
        return 2

    # Project operations inspect only the active project root.  Downloads/global intake is
    # owned by the background/manual Vault intake service and is never polled, queued, staged
    # or applied merely because a build/gate is running.
    if operation in CLEAN_OPERATIONS or operation in PATCH_APPLY_OPERATIONS:
        if _ingest_root_drop(root) != 0:
            return 1

    do_clean = operation in CLEAN_OPERATIONS
    if do_clean and _print_hygiene("Pre-operation", root) != 0:
        return 1

    print(f"[FORGE] Operation host {VERSION}: {operation}", flush=True)
    rc = 1
    try:
        if operation == "patch-apply":
            rc = _apply_staged_updates(root, operation, child)
        else:
            if operation in PATCH_APPLY_OPERATIONS:
                patch_rc = _apply_staged_updates(root, operation, child)
                if patch_rc != 0:
                    return patch_rc
            rc = _run(child, root)

        if rc == 0 and operation == "patch-apply":
            try:
                reconciled = reconcile_project(root)
                promoted = int(reconciled.get("reconciled", 0) or 0)
                if promoted:
                    print(f"[PASS] Forge reconciled {promoted} applied patch(es) into the durable Library archive.", flush=True)
            except Exception as exc:
                print(f"[WARN] Patch applied, but Forge reconciliation needs attention: {exc}", flush=True)
    finally:
        if do_clean:
            clean_rc = _print_hygiene("Post-operation", root)
            if rc == 0 and clean_rc != 0:
                rc = clean_rc
    if rc == 0 and operation == "full":
        try:
            green = certify_green(root, gate="full")
            print(
                f"[PASS] Forge GREEN authority recorded: {green.get('sourceFileCount', 0)} governed file(s) -> {green.get('path')}",
                flush=True,
            )
        except Exception as exc:
            print(f"[FAIL] Full gate passed but Forge could not persist GREEN authority: {exc}", flush=True)
            return 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
