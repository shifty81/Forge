#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PCCSurfaceCommon import BackendClient, ProjectContract, ProjectRegistry

FORGE_UNIVERSAL_TOOLING_VERSION = "FORGE-UNIVERSAL-TOOLING-0.4.6"


def capability_row(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    contract = ProjectContract.load(root)
    backend = BackendClient(root, contract)
    discovery = contract.raw.get("_pccDiscovery") or {}
    tool_authority = str(discovery.get("provider") or (contract.raw.get("root_control_center") or {}).get("launcher") or "")
    return {
        "projectId": contract.project_id,
        "name": contract.name,
        "kind": contract.kind,
        "root": str(root),
        "provider": backend.provider_label,
        "toolAuthority": tool_authority,
        "build": backend.supports("build"),
        "release": backend.supports("build-release"),
        "quick": backend.supports("quick"),
        "full": backend.supports("full"),
        "run": backend.supports("launch-gui"),
        "test": any(key.startswith("test.") for key in contract.command_keys),
        "commands": len(contract.commands),
    }


def capability_matrix(registry: ProjectRegistry | None = None) -> list[dict[str, Any]]:
    registry = registry or ProjectRegistry()
    rows: list[dict[str, Any]] = []
    for entry in registry.entries():
        if not entry.root.is_dir():
            rows.append({
                "projectId": entry.project_id, "name": entry.name, "kind": entry.kind,
                "root": str(entry.root), "provider": "missing root", "build": False,
                "release": False, "quick": False, "full": False, "run": False,
                "test": False, "commands": 0, "error": "project root missing",
            })
            continue
        try:
            rows.append(capability_row(entry.root))
        except Exception as exc:
            rows.append({
                "projectId": entry.project_id, "name": entry.name, "kind": entry.kind,
                "root": str(entry.root), "provider": "unavailable", "build": False,
                "release": False, "quick": False, "full": False, "run": False,
                "test": False, "commands": 0, "error": str(exc),
            })
    return rows


def build_all_registered(
    registry: ProjectRegistry | None = None,
    *,
    emit: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Sequentially build every registered project with a supported build operation.

    Project-native providers and declared project.control.json commands remain authoritative;
    the universal auto-adapter is used only when the project has no stronger provider.
    """
    registry = registry or ProjectRegistry()
    emit = emit or (lambda _line: None)
    results: list[dict[str, Any]] = []
    for entry in registry.entries():
        if not entry.root.is_dir():
            results.append({"project": entry.name, "root": str(entry.root), "state": "SKIP", "reason": "missing root"})
            emit(f"[SKIP] {entry.name}: missing root\n")
            continue
        try:
            contract = ProjectContract.load(entry.root)
            backend = BackendClient(entry.root, contract)
        except Exception as exc:
            results.append({"project": entry.name, "root": str(entry.root), "state": "FAIL", "reason": str(exc)})
            emit(f"[FAIL] {entry.name}: provider discovery failed: {exc}\n")
            continue
        if not backend.supports("build"):
            results.append({"project": entry.name, "root": str(entry.root), "state": "SKIP", "reason": "no build capability"})
            emit(f"[SKIP] {entry.name}: no build capability discovered\n")
            continue
        emit(f"\n=== BUILD {entry.name} ===\nProvider: {backend.provider_label}\nRoot: {entry.root}\n")
        try:
            proc = backend.popen("build")
            if proc.stdout is not None:
                for line in proc.stdout:
                    emit(line if line.endswith("\n") else line + "\n")
            rc = proc.wait()
            state = "PASS" if rc == 0 else "FAIL"
            results.append({"project": entry.name, "root": str(entry.root), "state": state, "returnCode": rc, "provider": backend.provider_label})
            emit(f"[{state}] {entry.name} build exited {rc}\n")
        except Exception as exc:
            results.append({"project": entry.name, "root": str(entry.root), "state": "FAIL", "reason": str(exc), "provider": backend.provider_label})
            emit(f"[FAIL] {entry.name}: {exc}\n")
    failed = [r for r in results if r.get("state") == "FAIL"]
    passed = [r for r in results if r.get("state") == "PASS"]
    skipped = [r for r in results if r.get("state") == "SKIP"]
    return {"passed": len(passed), "failed": len(failed), "skipped": len(skipped), "results": results}
