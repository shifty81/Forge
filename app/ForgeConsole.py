#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from ForgeHealth import evaluate_project
from VaultIntake import reconcile_project, scan_intake, stage_for_project
from VaultPaths import vault_root
from VaultPatchEngine import restart_marker_path
from ForgeVersion import VERSION as FORGE_VERSION
from ForgeSourceControl import status as source_status
from PCCSurfaceCommon import BackendClient, ProjectContract, ProjectRegistry, SurfaceError, latest_debug_bundle, open_path

CONSOLE_VERSION = f"FORGE-CONSOLE-{FORGE_VERSION}"


def _ansi_enabled() -> bool:
    return sys.stdout.isatty() and str(os.environ.get("NO_COLOR") or "").strip() == ""


def _token(text: str, kind: str) -> str:
    if not _ansi_enabled():
        return text
    colors = {"pass": "\x1b[92m", "fail": "\x1b[91m", "warn": "\x1b[93m", "info": "\x1b[96m"}
    return colors.get(kind, "") + text + "\x1b[0m"


def _line(label: str, value: str) -> str:
    return f" {label:<11}: {value}"


def _status_lines(root: Path, contract: ProjectContract, backend: BackendClient) -> list[str]:
    try:
        status = backend.status()
    except Exception:
        status = evaluate_project(root, contract).status
    git = status.get("git") or {}
    patches = status.get("patches") or {}
    hygiene = status.get("hygiene") or {}
    source = status.get("sourceControl") or source_status(root)
    health = evaluate_project(root, contract)

    if git.get("gitReady"):
        git_text = "Clean" if git.get("clean") else "Modified"
        branch = str(git.get("branch") or "<none>")
        head = str(git.get("headShort") or "<unborn>")
        git_text = f"{branch} / {git_text} @ {head}"
    else:
        git_text = "Not ready"
    green = "MATCH" if git.get("greenMatch") else ("STALE" if git.get("greenMarker") else "NONE")
    pending = int(patches.get("pending", 0) or 0)
    invalid = int(patches.get("invalid", 0) or 0)
    updates = f"{pending} pending" + (f", {invalid} invalid" if invalid else "")
    return [
        _line("Repository", str(root)),
        _line("Project", f"{contract.name} ({contract.kind})"),
        _line("Health", health.label),
        _line("Git", git_text),
        _line("GREEN", green),
        _line("GitHub", "Configured" if source.get("githubConfigured") else "Needs normalization"),
        _line("Forgejo", "Configured" if source.get("forgejoConfigured") else "Needs normalization"),
        _line("Updates", updates),
        _line("Hygiene", "Clean" if hygiene.get("clean", True) else "WARN"),
        _line("Provider", backend.provider_label),
        _line("Vault", str(vault_root())),
    ]


def _run_backend(backend: BackendClient, command: str, extra: Sequence[str] = ()) -> int:
    if not backend.supports(command):
        print(f"[{_token('FAIL', 'fail')}] Command is not supported by this project: {command}")
        return 2
    proc = backend.popen(command, extra)
    assert proc.stdout is not None
    for line in proc.stdout:
        # Provider output is left intact except the semantic result word itself.
        raw = line.rstrip("\r\n")
        for word, kind in (("PASS", "pass"), ("FAIL", "fail"), ("GREEN", "pass"), ("WARN", "warn")):
            if _ansi_enabled() and word in raw:
                raw = raw.replace(word, _token(word, kind))
        print(raw)
    return int(proc.wait())


def _apply_updates(root: Path, backend: BackendClient) -> int:
    staged = stage_for_project(root)
    count = int(staged.get("staged", 0) or 0)
    print(f"[{_token('INFO', 'info')}] Vault staged {count} queued Vault patch(es).")
    rc = _run_backend(backend, "patch-apply")
    if rc == 0:
        result = reconcile_project(root)
        print(f"[{_token('PASS', 'pass')}] Reconciled {result.get('reconciled', 0)} applied patch(es) into Vault Library.")
        if restart_marker_path().is_file():
            print(f"[{_token('WARN', 'warn')}] Forge itself was updated. Exit and reopen Forge to load the new application version.")
    return rc


def _registered_commands(contract: ProjectContract) -> None:
    if not contract.commands:
        print("No registered commands discovered.")
        return
    print("\n REGISTERED COMMANDS")
    print("-" * 72)
    for idx, cmd in enumerate(contract.commands, 1):
        print(f" {idx:>2}. {cmd.key:<28} {cmd.label} [{cmd.risk}]")


def _choose_project(registry: ProjectRegistry, current: Path) -> Path:
    entries = [entry for entry in registry.entries() if entry.root.is_dir()]
    if not entries:
        print("No other registered projects.")
        return current
    print("\n REGISTERED PROJECTS")
    print("-" * 72)
    for index, entry in enumerate(entries, 1):
        marker = "*" if entry.root.resolve() == current.resolve() else " "
        print(f" {index:>2}. {marker} {entry.name:<24} {entry.root}")
    raw = input("Select project [Enter=cancel]: ").strip()
    if not raw:
        return current
    try:
        selected = entries[int(raw) - 1]
    except Exception:
        print(f"[{_token('WARN', 'warn')}] Invalid selection.")
        return current
    registry.touch(selected.root)
    return selected.root.resolve()


def _header(root: Path, contract: ProjectContract, backend: BackendClient) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 72)
    print(f" FORGE  v{FORGE_VERSION}")
    print("=" * 72)
    for line in _status_lines(root, contract, backend):
        print(line)
    print("-" * 72)
    print("  1. FULL QUALITY GATE / CERTIFY GREEN")
    print("  2. COMMIT + PUSH CURRENT GREEN")
    print()
    print("  3. Build & verify")
    print("  4. Run & play")
    print("  5. Apply queued updates")
    print("  6. Registered project commands")
    print("  7. Maintenance & diagnostics")
    print("  8. Vault intake (root queue + Downloads catalog)")
    print("  9. Switch registered project")
    print("  0. Exit")
    print("-" * 72)


def run_console(initial_root: Path) -> int:
    registry = ProjectRegistry()
    root = initial_root.resolve()
    while True:
        try:
            contract = ProjectContract.load(root)
            backend = BackendClient(root, contract)
        except Exception as exc:
            print(f"[{_token('FAIL', 'fail')}] Forge could not bind project authority: {exc}")
            return 1
        _header(root, contract, backend)
        choice = input("Select an option: ").strip()
        if choice == "0":
            return 0
        if choice == "1":
            _run_backend(backend, "full")
        elif choice == "2":
            _run_backend(backend, "commit-push-green")
        elif choice == "3":
            _run_backend(backend, "build")
        elif choice == "4":
            _run_backend(backend, "launch-gui")
        elif choice == "5":
            _apply_updates(root, backend)
        elif choice == "6":
            _registered_commands(contract)
            raw = input("Command key [Enter=back]: ").strip()
            if raw:
                _run_backend(backend, raw)
        elif choice == "7":
            print(" 1. Doctor / project health\n 2. Debug bundle\n 3. Open latest debug bundle\n 0. Back")
            sub = input("Select: ").strip()
            if sub == "1": _run_backend(backend, "doctor")
            elif sub == "2": _run_backend(backend, "debug-bundle")
            elif sub == "3":
                latest = latest_debug_bundle(root)
                if latest: open_path(latest)
                else: print("No debug bundle found.")
        elif choice == "8":
            result = scan_intake(extra_roots=(root, Path(__file__).resolve().parents[1]), force_stable=True, remove_source=True)
            print(json.dumps({"queued": sum(1 for x in result["ingested"] if str(x.get("state","")).upper()=="QUEUED"), "available": sum(1 for x in result["ingested"] if str(x.get("state","")).upper()=="AVAILABLE"), "review": len(result.get("reviews") or []) + sum(1 for x in result["ingested"] if str(x.get("state","")).upper()=="REVIEW"), "waiting": len(result["skipped"]), "blocking_root_errors": len(result["errors"])}, indent=2))
            print(f"Vault: {vault_root()}")
        elif choice == "9":
            root = _choose_project(registry, root)
        else:
            print(f"[{_token('WARN', 'warn')}] Unknown option.")
        if choice != "9":
            input("\nPress Enter to return to Forge...")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Forge emergency/console Project Control Center")
    ap.add_argument("--root", required=True)
    ap.add_argument("--command", help="Run one backend command non-interactively")
    ap.add_argument("--self-test", action="store_true")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).expanduser().resolve()
    contract = ProjectContract.load(root)
    backend = BackendClient(root, contract)
    if ns.self_test:
        print(f"PASS console-version={CONSOLE_VERSION}")
        print(f"PASS project={contract.project_id}")
        print(f"PASS provider={backend.provider_label}")
        return 0
    if ns.command:
        return _run_backend(backend, ns.command)
    return run_console(root)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SurfaceError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise SystemExit(130)
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
