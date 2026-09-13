#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Sequence

from PCCProjectDiscovery import discover_project_contract_data
from PCCRepoHygiene import prepare
from ForgePYIntake import reconcile_project, scan_roots, stage_for_project
from ForgePYPatchEngine import apply_transport, can_apply_transport
from ForgeGreen import certify_green

VERSION = "FORGE-OPERATION-HOST-1.2-F797"

CLEAN_OPERATIONS = {
    "full", "quick", "fast", "build", "build-release", "patch-apply", "self-test",
    "commit-green", "commit-push-green", "push", "git-pull",
    "debug-bundle", "doctor", "root-hygiene", "root-hygiene-fix",
}

# Queued updates are never adopted by ordinary build/gate operations.
AUTO_PATCH_OPERATIONS: set[str] = set()


def _print_hygiene(label: str, root: Path) -> int:
    try:
        result = prepare(root, apply=True)
    except Exception as exc:
        print(f"[FAIL] {label} repository transport hygiene failed: {exc}", flush=True)
        return 1
    moved = int(result.get("moved", 0) or 0)
    if moved:
        print(f"[PASS] {label} repository transport hygiene moved {moved} operational artifact(s).", flush=True)
    else:
        print(f"[PASS] {label} repository transport hygiene clean.", flush=True)
    pending = result.get("pendingPatchTransports") or []
    if pending:
        print(f"[INFO] {len(pending)} pending patch transport(s) preserved for ForgePY intake.", flush=True)
    return 0


def _run(argv: Sequence[str], root: Path) -> int:
    env = os.environ.copy()
    env["PCC_OPERATION_HOST_ACTIVE"] = "1"
    env["VAULT_OPERATION_HOST_ACTIVE"] = "1"
    env["FORGE_OPERATION_HOST_ACTIVE"] = "1"
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.Popen(list(argv), cwd=str(root), stdin=subprocess.DEVNULL, env=env)
    return int(proc.wait())


def _provider_variant(child: Sequence[str], current_operation: str, replacement: str) -> list[str]:
    argv = list(child)
    for index in range(min(8, len(argv))):
        if argv[index] == current_operation:
            argv[index] = replacement
            return argv
    raise RuntimeError(f"cannot derive provider operation {replacement!r} from child argv")


def _project_command_keys(root: Path) -> set[str]:
    try:
        data = discover_project_contract_data(root)
    except Exception:
        return set()
    return {str(item.get("key") or "").casefold() for item in data.get("commands", []) if isinstance(item, dict)}


def _project_has_patch_authority(root: Path) -> bool:
    keys = _project_command_keys(root)
    return "patch.apply" in keys or "patch.apply-staged" in keys


def _project_has_recovery_authority(root: Path) -> bool:
    keys = _project_command_keys(root)
    return bool(keys & {"recovery.restore", "recovery.undo-last", "patch.undo", "patch.rollback"})


def _ingest_root_drop(root: Path) -> int:
    """Respect project-owned root-drop authority before generic Forge intake.

    Mature internal PCCs intentionally watch the project root/updates inbox. Moving the
    transport into Vault before the project provider starts breaks that contract. When the
    project exposes both patch and recovery authority, preserve the exact bytes in place and
    let explicit project tooling validate/apply them. Generic projects keep the Forge queue.
    """
    if _project_has_patch_authority(root) and _project_has_recovery_authority(root):
        try:
            from ForgeProjectPCC import root_patch_transports
            native = root_patch_transports(root, include_inbox=False)
        except Exception:
            native = []
        if native:
            print(
                f"[PASS] Project-owned root-drop authority detected; preserved {len(native)} patch transport(s) "
                "in place for the internal PCC. ForgePY did not move or rewrite them.",
                flush=True,
            )
            return 0
    try:
        result = scan_roots((root,), force_stable=True, remove_source=True, trusted_roots=(root,))
    except Exception as exc:
        print(f"[FAIL] Forge active-root intake preflight failed: {exc}", flush=True)
        return 1
    for item in result.get("ingested", []):
        state = str(item.get("state") or "").upper()
        if state == "QUEUED":
            print(f"[PASS] Forge queued {item.get('patch_id')} for this project; source is unchanged.", flush=True)
        else:
            print(f"[INFO] Forge root intake cataloged {item.get('patch_id')} as {state or 'NONEXECUTABLE'}.", flush=True)
    for item in result.get("errors", []):
        print(f"[FAIL] Forge active-root patch rejected {item.get('path')}: {item.get('error')}", flush=True)
    return 0 if not result.get("errors") else 1


def _staged_sources(staged: dict[str, object]) -> tuple[list[Path], list[Path], list[str]]:
    universal: list[Path] = []
    native: list[Path] = []
    errors: list[str] = []
    for row in list(staged.get("items") or []):
        source = Path(str(row.get("source") or "")).expanduser()
        if not source.is_file():
            errors.append(f"staged transport is missing: {source}")
            continue
        if can_apply_transport(source):
            universal.append(source.resolve())
        else:
            native.append(source.resolve())
    return universal, native, errors


def _apply_universal_batch(root: Path, sources: list[Path], project_id: str) -> tuple[int, Path | None]:
    from ForgePatchCheckpoint import create as create_checkpoint, mark as mark_checkpoint, restore as restore_checkpoint

    try:
        checkpoint_info = create_checkpoint(root, sources, project_id=project_id)
        checkpoint = Path(str(checkpoint_info["path"]))
        mark_checkpoint(checkpoint, "APPLYING")
        print(
            f"[PASS] Recovery checkpoint created before mutation: {checkpoint} "
            f"({checkpoint_info.get('files', 0)} touched path(s)).",
            flush=True,
        )
    except Exception as exc:
        print(f"[FAIL] Apply Updates stopped before mutation because recovery checkpoint creation failed: {exc}", flush=True)
        return 1, None

    for source in sources:
        try:
            receipt = apply_transport(source, root)
            print(f"[PASS] ForgePY applied {receipt.get('patchId') or source.name} transactionally.", flush=True)
        except Exception as exc:
            print(f"[FAIL] ForgePY patch engine failed: {exc}", flush=True)
            try:
                restored = restore_checkpoint(checkpoint)
                if restored.get("ok"):
                    print(f"[PASS] Entire update batch restored from checkpoint: {checkpoint}", flush=True)
                else:
                    print(f"[FAIL] Batch rollback needs attention: {restored.get('errors')}", flush=True)
            except Exception as rollback_exc:
                print(f"[FAIL] Batch rollback could not complete: {rollback_exc}", flush=True)
            return 1, checkpoint

    mark_checkpoint(checkpoint, "APPLIED_AWAITING_GATE")
    return 0, checkpoint


def _apply_staged_updates(root: Path, operation: str, child: Sequence[str]) -> tuple[int, Path | None]:
    try:
        staged = stage_for_project(root, compatibility_inbox=False)
    except Exception as exc:
        print(f"[FAIL] ForgePY could not validate the approved patch queue: {exc}", flush=True)
        return 1, None

    count = int(staged.get("staged", 0) or 0)
    if count == 0:
        # An explicit Apply Updates action may delegate the same root/inbox transport
        # directly to a mature project-owned PCC. This keeps Havenwild/Subspace-style
        # standalone root-drop workflows interoperable with ForgePY without rewrapping bytes.
        if _project_has_patch_authority(root) and _project_has_recovery_authority(root):
            try:
                from ForgeProjectPCC import root_patch_transports
                native_pending = root_patch_transports(root, include_inbox=True)
            except Exception:
                native_pending = []
            if native_pending:
                print(
                    f"[PASS] Explicit Apply Updates delegated {len(native_pending)} project-owned root/inbox "
                    "transport(s) to the internal PCC; exact bytes were preserved.",
                    flush=True,
                )
                apply_child = _provider_variant(child, operation, "patch-apply")
                return _run(apply_child, root), None
        print("[INFO] No approved updates are queued for this project.", flush=True)
        return 0, None

    print(f"[INFO] Explicit Apply Updates selected: preflighting {count} queued patch(es) before mutation.", flush=True)
    universal, native, errors = _staged_sources(staged)
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", flush=True)
        print("[FAIL] No project source was changed.", flush=True)
        return 1, None

    # Never partially apply one authority and only then discover that a second
    # authority cannot safely handle the rest of the same queue.
    if universal and native:
        print(
            "[FAIL] The staged batch mixes ForgePY-universal and project-native transports. "
            "Nothing was applied. Review/unstage the batch so one recovery authority owns the transaction.",
            flush=True,
        )
        return 1, None

    checkpoint: Path | None = None
    if universal:
        try:
            project_id = str((discover_project_contract_data(root).get("project") or {}).get("id") or root.name)
        except Exception:
            project_id = root.name
        rc, checkpoint = _apply_universal_batch(root, universal, project_id)
        if rc != 0:
            return rc, checkpoint
    elif native:
        if not _project_has_patch_authority(root):
            print(
                f"[FAIL] {len(native)} staged transport(s) require project-specific patch authority. "
                "Nothing was applied.",
                flush=True,
            )
            return 1, None
        if not _project_has_recovery_authority(root):
            print(
                "[FAIL] Project-native patch authority has no declared recovery/rollback capability. "
                "ForgePY will not mutate source without a recovery boundary.",
                flush=True,
            )
            return 1, None
        compat = stage_for_project(root, compatibility_inbox=True)
        if int(compat.get("staged", 0) or 0) <= 0:
            print("[FAIL] No compatibility transports were staged for the project-native authority.", flush=True)
            return 1, None
        print("[PASS] Project-native patch + recovery authority accepted the staged batch.", flush=True)
        apply_child = _provider_variant(child, operation, "patch-apply")
        rc = _run(apply_child, root)
        if rc != 0:
            return rc, None

    try:
        reconcile_project(root)
    except Exception as exc:
        print(f"[WARN] Applied update reconciliation needs attention: {exc}", flush=True)
    return 0, checkpoint


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ForgePY universal operation host")
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
        print("[FAIL] ForgePY operation host received no provider command.", flush=True)
        return 2

    if operation in CLEAN_OPERATIONS:
        if _ingest_root_drop(root) != 0:
            return 1
        if _print_hygiene("Pre-operation", root) != 0:
            return 1

    print(f"[FORGE] Operation host {VERSION}: {operation}", flush=True)
    rc = 1
    checkpoint: Path | None = None
    try:
        if operation == "patch-apply":
            rc, checkpoint = _apply_staged_updates(root, operation, child)
            if rc == 0:
                try:
                    full_child = _provider_variant(child, operation, "full")
                    print("[INFO] Updates applied; starting authoritative Full Gate.", flush=True)
                    rc = _run(full_child, root)
                except Exception as exc:
                    print(f"[FAIL] Updates applied but Full Gate could not be derived: {exc}", flush=True)
                    rc = 1
                if rc != 0 and checkpoint is not None:
                    try:
                        from ForgePatchCheckpoint import mark
                        mark(checkpoint, "GATE_FAILED_RECOVERY_AVAILABLE", detail="Authoritative Full Gate failed after update apply")
                        print(f"[WARN] Failed updated state preserved. Recovery checkpoint: {checkpoint}", flush=True)
                    except Exception as exc:
                        print(f"[WARN] Could not annotate recovery checkpoint: {exc}", flush=True)
        else:
            # Declared asset dependencies are hydrated from exact hash-bound Vault/backup
            # authority before the project's Full Gate runs. Projects with no Forge asset
            # requirement manifest are unaffected.
            if operation == "full":
                try:
                    from ForgeAssetResolver import hydrate
                    assets = hydrate(root, apply=True)
                    required = int(assets.get("required", 0) or 0)
                    missing = int(assets.get("missing", 0) or 0)
                    if required:
                        print(f"[INFO] Forge asset hydration preflight: {required - missing}/{required} READY; report={assets.get('report')}", flush=True)
                    if missing:
                        for error in assets.get("errors", [])[:20]:
                            print(f"[FAIL] Asset hydration: {error}", flush=True)
                        print("[FAIL] Full Gate stopped before project execution because required assets are unresolved.", flush=True)
                        return 1
                except Exception as exc:
                    print(f"[FAIL] Forge asset hydration preflight failed: {exc}", flush=True)
                    return 1
            rc = _run(child, root)
            if rc != 0 and operation == "full":
                try:
                    from ForgeAssetResolver import diagnose_recent_logs
                    report = diagnose_recent_logs(root)
                    hits = [row for row in report.get("mentions", []) if int(row.get("candidateCount", 0) or 0) > 0]
                    if hits:
                        print(f"[INFO] Vault asset recovery found {len(hits)} logged asset mention(s) with candidate sources; report={report.get('report')}", flush=True)
                        for row in hits[:8]:
                            print(f"[INFO] Asset candidate: {row.get('name')} -> {row.get('candidateCount')} Vault/backup match(es)", flush=True)
                except Exception as exc:
                    print(f"[WARN] Post-failure asset recovery diagnostics could not complete: {exc}", flush=True)
    finally:
        if operation in CLEAN_OPERATIONS:
            clean_rc = _print_hygiene("Post-operation", root)
            if rc == 0 and clean_rc != 0:
                rc = clean_rc

    if rc == 0 and operation in {"full", "patch-apply"}:
        try:
            green = certify_green(root, gate="full")
            print(f"[PASS] ForgePY GREEN authority recorded: {green.get('path')}", flush=True)
            if operation == "patch-apply" and checkpoint is not None:
                try:
                    from ForgePatchCheckpoint import mark
                    mark(checkpoint, "GREEN", detail=str(green.get("path") or ""))
                except Exception as exc:
                    print(f"[WARN] GREEN passed but checkpoint state could not be finalized: {exc}", flush=True)
        except Exception as exc:
            print(f"[FAIL] Gate passed but GREEN authority could not be persisted: {exc}", flush=True)
            if operation == "patch-apply" and checkpoint is not None:
                try:
                    from ForgePatchCheckpoint import mark
                    mark(checkpoint, "GATE_FAILED_RECOVERY_AVAILABLE", detail=f"GREEN persistence failed: {exc}")
                except Exception:
                    pass
            return 1
    elif operation == "patch-apply" and checkpoint is not None:
        try:
            from ForgePatchCheckpoint import mark
            # Preserve the failed post-apply state and checkpoint. Do not silently roll
            # back a gate failure; operator/Cortex can inspect evidence and explicitly restore.
            current = mark(checkpoint, "GATE_FAILED_RECOVERY_AVAILABLE", detail="Update apply did not certify GREEN")
            del current
        except Exception:
            pass
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
