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
from VaultPatchEngine import apply_inbox
from ForgeGreen import certify_green

VERSION = "FORGE-OPERATION-HOST-0.8"

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
        print(f"[PASS] Forge root-drop queued {item.get('patch_id')}.", flush=True)
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
    queued = len(result.get("ingested") or [])
    rejected = len(result.get("errors") or [])
    if queued:
        print(f"[PASS] Forge Downloads intake queued {queued} patch transport(s).", flush=True)
    if rejected:
        print(f"[WARN] Forge Downloads intake has {rejected} rejected/review transport(s); active project gate continues.", flush=True)


def _universal_apply(root: Path) -> tuple[int, int]:
    try:
        result = apply_inbox(root)
    except Exception as exc:
        print(f"[FAIL] Forge universal patch engine failed and rolled back: {exc}", flush=True)
        return 1, 0
    applied = int(result.get("applied", 0) or 0)
    skipped = int(result.get("skipped", 0) or 0)
    if applied:
        print(f"[PASS] Forge universal patch engine applied {applied} patch(es) transactionally.", flush=True)
    return 0, skipped


def _apply_staged_updates(root: Path, operation: str, child: Sequence[str]) -> int:
    try:
        staged = stage_for_project(root)
    except Exception as exc:
        print(f"[FAIL] Forge could not stage queued patch(es): {exc}", flush=True)
        return 1
    count = int(staged.get("staged", 0) or 0)
    if count == 0:
        return 0
    print(f"[INFO] Forge staged {count} queued patch(es) for the next {operation} operation.", flush=True)

    # Prefer an established project-native authority when one exists. That preserves stronger
    # project semantics during migration. Otherwise the universal transaction engine handles
    # standard Vault patch transports, which is what enables arbitrary newly-registered projects.
    if _project_has_patch_authority(root):
        try:
            apply_child = _provider_variant(child, operation, "patch-apply")
        except Exception as exc:
            print(f"[FAIL] Could not invoke project patch authority: {exc}", flush=True)
            return 1
        rc = _run(apply_child, root)
        if rc != 0:
            print(f"[FAIL] Project patch authority rejected/failed queued patch(es), exit={rc}.", flush=True)
            return rc
    else:
        rc, skipped = _universal_apply(root)
        if rc != 0:
            return rc
        if skipped:
            print(f"[FAIL] {skipped} staged patch(es) require a project-specific patch authority or a Vault patch manifest.", flush=True)
            return 1

    try:
        reconciled = reconcile_project(root)
        promoted = int(reconciled.get("reconciled", 0) or 0)
        if promoted:
            print(f"[PASS] Forge reconciled {promoted} applied patch(es) into the durable Library archive.", flush=True)
    except Exception as exc:
        print(f"[WARN] Patch applied, but Forge reconciliation needs attention: {exc}", flush=True)
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
            try:
                staged = stage_for_project(root)
                count = int(staged.get("staged", 0) or 0)
                if count:
                    print(f"[INFO] Forge staged {count} queued patch(es) for explicit apply.", flush=True)
            except Exception as exc:
                print(f"[FAIL] Forge could not stage queued patch(es): {exc}", flush=True)
                return 1

            if _project_has_patch_authority(root):
                rc = _run(child, root)
            else:
                rc, skipped = _universal_apply(root)
                if rc == 0 and skipped:
                    print(f"[FAIL] {skipped} patch(es) cannot be handled by the universal patch engine.", flush=True)
                    rc = 1
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
