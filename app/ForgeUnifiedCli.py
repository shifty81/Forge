#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ForgeUnifiedServices import operations, project, vault

CLI_VERSION = "FORGEPY-UNIFIED-CLI-2.0-F740"


def _dump(value: Any, *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(value, indent=2, sort_keys=True, default=str))
    elif isinstance(value, dict):
        for key, val in value.items():
            print(f"{key}: {val}")
    elif isinstance(value, list):
        for row in value:
            print(row)
    else:
        print(value)


def _normalize_global_options(argv: list[str]) -> list[str]:
    """Allow --root/--json/--stream-json after normal command groups.

    `command run` deliberately keeps remainder arguments untouched because project
    commands may legitimately own flags with the same names.
    """
    if not argv or (len(argv) >= 2 and argv[0] == "command" and argv[1] == "run"):
        return list(argv)
    front: list[str] = []
    rest: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"--json", "--stream-json"}:
            front.append(token); index += 1; continue
        if token == "--root" and index + 1 < len(argv):
            front.extend([token, argv[index + 1]]); index += 2; continue
        if token.startswith("--root="):
            front.append(token); index += 1; continue
        rest.append(token); index += 1
    return front + rest


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="ForgePY unified CLI")
    ap.add_argument("--root", help="Active project root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stream-json", action="store_true")
    sub = ap.add_subparsers(dest="group", required=True)

    ui_p = sub.add_parser("ui")
    ui_sub = ui_p.add_subparsers(dest="action", required=True)
    ui_sub.add_parser("workflow")

    source_p = sub.add_parser("source")
    source_sub = source_p.add_subparsers(dest="action", required=True)
    source_sub.add_parser("authority")

    vault_p = sub.add_parser("vault")
    vault_sub = vault_p.add_subparsers(dest="action", required=True)
    vault_sub.add_parser("projects")
    vault_sub.add_parser("workflow")
    scan_p = vault_sub.add_parser("scan", help="Use ForgePY's existing VaultDriveIndex catalog scanner")
    scan_p.add_argument("--scan-root", help="Directory to inventory (defaults to configured scan root)")
    scan_p.add_argument("--max-dirs", type=int, default=500000)
    scan_p.add_argument("--max-depth", type=int, default=24)
    vault_sub.add_parser("catalog-status", help="Read the existing Vault drive catalog")

    project_p = sub.add_parser("project")
    project_sub = project_p.add_subparsers(dest="action", required=True)
    audit_p = project_sub.add_parser("audit")
    audit_p.add_argument("--deep", action="store_true")
    handoff_p = project_sub.add_parser("handoffs")
    handoff_p.add_argument("--deep", action="store_true")
    project_sub.add_parser("capabilities")

    performance_p = sub.add_parser("performance")
    performance_sub = performance_p.add_subparsers(dest="action", required=True)
    performance_sub.add_parser("audit")
    recent_p = performance_sub.add_parser("recent")
    recent_p.add_argument("--slow-only", action="store_true")
    recent_p.add_argument("--limit", type=int, default=100)
    performance_sub.add_parser("load")

    executable_p = sub.add_parser("executable")
    executable_sub = executable_p.add_subparsers(dest="action", required=True)
    executable_sub.add_parser("preflight")
    build_exe_p = executable_sub.add_parser("build")
    build_exe_p.add_argument("--skip-installer", action="store_true")
    executable_sub.add_parser("installer-script")

    workspace_p = sub.add_parser("workspace")
    workspace_sub = workspace_p.add_subparsers(dest="action", required=True)
    workspace_sub.add_parser("performance")

    patch_p = sub.add_parser("patch")
    patch_sub = patch_p.add_subparsers(dest="action", required=True)
    queue_p = patch_sub.add_parser("queue")
    queue_p.add_argument("file")

    command_p = sub.add_parser("command")
    command_sub = command_p.add_subparsers(dest="action", required=True)
    run_p = command_sub.add_parser("run")
    run_p.add_argument("key")
    run_p.add_argument("extra", nargs=argparse.REMAINDER)

    for name, key in (
        ("full", "gate.full"), ("build", "build.default"),
        ("run", "run.default"), ("apply-updates", "patch.apply-staged"),
    ):
        p = sub.add_parser(name)
        p.set_defaults(canonical_command=key)
    return ap


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    ns = build_parser().parse_args(_normalize_global_options(raw))
    root = Path(ns.root).expanduser().resolve() if ns.root else None

    if ns.group == "ui" and ns.action == "workflow":
        from ForgeUiWorkflowModel import surface_model
        _dump(surface_model(), json_mode=True)
        return 0
    if ns.group == "source" and ns.action == "authority":
        from ForgeSourceTreePolicy import report
        _dump(report(root or Path.cwd()), json_mode=True)
        return 0

    if ns.group == "vault" and ns.action == "scan":
        from VaultDriveIndex import scan
        from VaultPaths import configured_scan_roots
        configured = configured_scan_roots()
        if not ns.scan_root and not configured:
            print("[FAIL] No configured scan root; pass --scan-root", file=sys.stderr)
            return 4
        selected = Path(ns.scan_root) if ns.scan_root else configured[0]
        if not selected.is_dir():
            print(f"[FAIL] Scan root does not exist: {selected}", file=sys.stderr)
            return 4
        def progress(event: dict[str, Any]) -> None:
            print(f"[SCAN] {event.get('phase')} dirs={event.get('directories', 0)} files={event.get('files', 0)} entries={event.get('entries', 0)}", file=sys.stderr, flush=True)
        result = scan(selected, max_dirs=max(1, ns.max_dirs), max_depth=max(0, ns.max_depth), progress=progress)
        _dump({k: v for k, v in result.items() if k != "records"}, json_mode=ns.json or ns.stream_json)
        return 11 if result.get("truncated") else 0
    if ns.group == "vault" and ns.action == "catalog-status":
        from VaultDriveIndex import latest_summary
        _dump(latest_summary(), json_mode=ns.json or ns.stream_json)
        return 0
    if ns.group == "vault" and ns.action == "projects":
        _dump(vault.projects(), json_mode=ns.json)
        return 0
    if ns.group == "vault" and ns.action == "workflow":
        _dump(vault.workflow(), json_mode=True)
        return 0

    if ns.group == "performance":
        if ns.action == "audit":
            target = root or Path.cwd()
            from ForgePerformanceAudit import write_report
            _dump(write_report(target), json_mode=True)
            return 0
        if ns.action == "recent":
            from ForgePerformance import recent
            _dump(recent(ns.limit, slow_only=bool(ns.slow_only)), json_mode=True)
            return 0
        if ns.action == "load":
            from ForgeLoadCoordinator import COORDINATOR
            from ForgeOperationGuard import GUARD
            _dump({"load": COORDINATOR.snapshot(), "operations": GUARD.snapshot()}, json_mode=True)
            return 0

    if ns.group == "executable":
        target = root or Path.cwd()
        from ForgeExecutableSystem import build_distribution, generate_inno_script, preflight
        if ns.action == "preflight":
            result = preflight(target)
            _dump(result, json_mode=True)
            return 0 if result.get("ok") and not result.get("error") else 7
        if ns.action == "installer-script":
            _dump({"script": str(generate_inno_script(target))}, json_mode=True)
            return 0
        if ns.action == "build":
            result = build_distribution(
                target,
                approved=True,
                build_installer_if_available=not bool(ns.skip_installer),
            )
            _dump(result, json_mode=True)
            return 0 if result.get("ok") else 1

    if ns.group == "workspace" and ns.action == "performance":
        from ForgeWorkspacePerformance import policy
        _dump(policy(), json_mode=True)
        return 0

    if ns.group == "patch" and ns.action == "queue":
        result = vault.queue_patch(Path(ns.file))
        _dump(result, json_mode=True if ns.stream_json else ns.json)
        return 0 if result.get("ok") and not result.get("error") else 7

    if ns.group == "project":
        if root is None:
            raise SystemExit("--root is required for project operations")
        if ns.action == "audit":
            _dump(project.audit(root, deep=ns.deep), json_mode=True)
        elif ns.action == "handoffs":
            _dump(project.handoffs(root, deep=ns.deep), json_mode=True)
        elif ns.action == "capabilities":
            _dump(project.capabilities(root), json_mode=ns.json)
        return 0

    key = getattr(ns, "canonical_command", "")
    extra: list[str] = []
    if ns.group == "command" and ns.action == "run":
        key = ns.key
        extra = list(ns.extra or [])
    if key:
        if root is None:
            raise SystemExit("--root is required for command execution")
        def emit(row: dict[str, Any]) -> None:
            if ns.stream_json:
                print(json.dumps(row, sort_keys=True), flush=True)
            elif row.get("message"):
                print(row["message"], flush=True)
        result = operations.run(root, key, extra=extra, initiator="cli", emit=emit)
        if not ns.stream_json:
            _dump(result, json_mode=ns.json)
        code = result.get("returncode")
        return int(code) if isinstance(code, int) and code != 0 else (0 if result.get("ok") and not result.get("error") else 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
