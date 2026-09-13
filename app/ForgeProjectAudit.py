#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ForgeProjectProtocol import effective_capabilities, integration_grade, matrix, normalize_key
from PCCSurfaceCommon import ProjectContract
from ForgePYPaths import ensure_artifact_project_tree

AUDIT_VERSION = "FORGEPY-PROJECT-AUDIT-1.1-F566"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _toolchain(root: Path) -> dict[str, Any]:
    markers = {
        "rust": (root / "Cargo.toml").is_file(),
        "cmake": (root / "CMakeLists.txt").is_file() or (root / "engine" / "CMakeLists.txt").is_file(),
        "dotnet": bool(list(root.glob("*.sln")) or list(root.glob("*.csproj"))),
        "gradle": any((root / x).exists() for x in ("gradlew", "gradlew.bat", "build.gradle", "settings.gradle")),
        "python": (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file(),
        "node": (root / "package.json").is_file(),
    }
    tools = {}
    for name in ("git", "cargo", "rustc", "cmake", "dotnet", "node", "npm", "java", "pwsh", "powershell"):
        tools[name] = shutil.which(name) or ""
    return {"markers": markers, "tools": tools}


def _source(root: Path) -> dict[str, Any]:
    try:
        from ForgePYSourceControl import status
        return dict(status(root) or {})
    except Exception as exc:
        return {"error": str(exc), "gitReady": (root / ".git").exists()}


def _updates(root: Path, contract: ProjectContract) -> dict[str, Any]:
    try:
        from ForgePYIntake import counts_for_project
        pending, invalid = counts_for_project(contract.project_id, contract.name, root.name)
        return {"queued": int(pending or 0), "invalid": int(invalid or 0)}
    except Exception as exc:
        return {"queued": 0, "invalid": 0, "error": str(exc)}


def _compatibility(contract: ProjectContract) -> dict[str, Any]:
    try:
        from ForgeCompatibilitySnapshot import status
        return dict(status(contract.project_id) or {})
    except Exception as exc:
        return {"state": "AUDIT REQUIRED", "error": str(exc)}


def _catalog(root: Path) -> dict[str, Any]:
    try:
        from PCCVaultCatalog import latest_summary
        return dict(latest_summary(root) or {})
    except Exception:
        return {}


def _provider(root: Path, contract: ProjectContract) -> dict[str, Any]:
    try:
        from PCCSurfaceCommon import BackendClient
        backend = BackendClient(root, contract)
        return {"mode": backend.provider_mode, "label": backend.provider_label}
    except Exception as exc:
        return {"mode": "unbound", "label": "", "error": str(exc)}


def audit(root: Path, *, deep: bool = False) -> dict[str, Any]:
    root = root.expanduser().resolve()
    contract = ProjectContract.load(root)
    raw_keys = [item.key for item in contract.commands]
    canonical = sorted({normalize_key(key) for key in raw_keys})
    protocol = integration_grade(canonical, audit_current=True, handoffs_current=False)
    result = {
        "schema": "forgepy.project-audit.v1",
        "version": AUDIT_VERSION,
        "capturedUtc": utc_now(),
        "deep": bool(deep),
        "project": {
            "id": contract.project_id,
            "name": contract.name,
            "kind": contract.kind,
            "root": str(root),
        },
        "provider": _provider(root, contract),
        "commands": raw_keys,
        "capabilities": canonical,
        "effectiveCapabilities": sorted(effective_capabilities(canonical)),
        "capabilityMatrix": matrix(raw_keys),
        "protocol": protocol,
        "source": _source(root),
        "updates": _updates(root, contract),
        "toolchain": _toolchain(root),
        "compatibility": _compatibility(contract),
        "catalog": _catalog(root),
        "discovery": dict(contract.raw.get("_pccDiscovery") or {}),
        "rootControlCenter": dict(contract.raw.get("root_control_center") or {}),
    }

    if deep:
        try:
            from VaultTooling import audit_project
            result["toolAudit"] = audit_project(root, contract.project_id)
        except Exception as exc:
            result["toolAudit"] = {"error": str(exc)}
        try:
            from PCCVaultCatalog import scan_project
            result["deepCatalog"] = scan_project(root, deep_hash=True)
        except TypeError:
            try:
                from PCCVaultCatalog import scan_project
                result["deepCatalog"] = scan_project(root)
            except Exception as exc:
                result["deepCatalog"] = {"error": str(exc)}
        except Exception as exc:
            result["deepCatalog"] = {"error": str(exc)}

    return result


def _md_bool(value: Any) -> str:
    return "YES" if bool(value) else "NO"


def _forgepy_handoff(a: dict[str, Any]) -> str:
    p = a["project"]
    proto = a["protocol"]
    provider = a["provider"]
    source = a["source"]
    return f"""# ForgePY Support Handoff — {p['name']}

Generated: {a['capturedUtc']}
Audit: {a['version']}

## Project identity

- Project ID: `{p['id']}`
- Kind: `{p['kind']}`
- Root: `{p['root']}`
- Integration grade: **{proto['grade']}**
- Provider: `{provider.get('label') or '<unbound>'}` ({provider.get('mode')})

## Source authority

- Git ready: {_md_bool(source.get('gitReady'))}
- Branch: `{source.get('branch') or '<unknown>'}`
- Clean: {_md_bool(source.get('clean'))}
- GitHub configured: {_md_bool(source.get('githubConfigured'))}
- ForgeGit configured: {_md_bool(source.get('forgeGitConfigured') or source.get('internalGitConfigured'))}

## Canonical capabilities

{chr(10).join('- `' + x + '`' for x in a['capabilities']) or '- None discovered'}

## Missing project-local standard capabilities

{chr(10).join('- `' + x + '`' for x in proto['standardMissing']) or '- None'}

## Missing project-local certification capabilities

{chr(10).join('- `' + x + '`' for x in proto['certifiedMissing']) or '- None'}

## Patch/update state

- Queued: {a['updates'].get('queued', 0)}
- Invalid/review: {a['updates'].get('invalid', 0)}

## ForgePY-side work

Use this handoff in the ForgePY repository/chat to add or adjust adapters, capability mappings,
GUI/CLI bindings, source-control integration, diagnostics, patch support, or tooling support.
ForgePY remains standalone; this report does not vendor ForgePY into the project.
"""


def _project_handoff(a: dict[str, Any]) -> str:
    p = a["project"]
    proto = a["protocol"]
    return f"""# {p['name']} → ForgePY Integration Handoff

Generated: {a['capturedUtc']}
Current ForgePY integration grade: **{proto['grade']}**

## Goal

Make this repository independently buildable/testable/runnable while exposing a clean ForgePY
Project Protocol contract. ForgePY is the universal front end; the project keeps its own
project-local CLI/PCC authority.

## Required standard capabilities still missing

{chr(10).join('- `' + x + '`' for x in proto['standardMissing']) or '- None'}

## Certification capabilities still missing

{chr(10).join('- `' + x + '`' for x in proto['certifiedMissing']) or '- None'}

## Project-side normalization checklist

- Keep one authoritative project-local CLI/PCC spine.
- Expose machine-readable status and health.
- Expose one authoritative Full Gate.
- Expose build, test and default run targets where applicable.
- Produce durable session logs and a canonical debug/support bundle.
- Preserve GREEN/source identity evidence.
- Keep Git/GitHub usable without ForgePY.
- Support ForgePY patch build/source preconditions.
- Keep artifacts and recovery evidence outside loose repository-root transport files.
- Return stable exit codes and stream UTF-8 output.
- Do not vendor the ForgePY application into this repository.

## Current discovered commands

{chr(10).join('- `' + x + '`' for x in a['commands']) or '- None'}

After project-side changes, re-run ForgePY Project Audit and certify the project.
"""



def _audit_target(root: Path, project_id: str) -> Path:
    tree = ensure_artifact_project_tree(project_id)
    return Path(tree["reports"]) / "forgepy-project-audit"


def handoffs_need_refresh(root: Path, *, max_age_seconds: float = 86400.0) -> bool:
    """Cheap freshness test used by project intake/activation.

    It intentionally avoids a project scan. Missing handoffs, an old audit, or project
    authority files newer than the audit are enough to request a background refresh.
    """
    import time

    root = root.expanduser().resolve()
    try:
        contract = ProjectContract.load(root)
        target = _audit_target(root, contract.project_id)
    except Exception:
        return True
    required = (
        target / "PROJECT_AUDIT.json",
        target / "FORGEPY_SUPPORT_HANDOFF.md",
        target / "PROJECT_INTEGRATION_HANDOFF.md",
        target / "PROJECT_INTELLIGENCE.json",
    )
    if any(not path.is_file() for path in required):
        return True
    try:
        audit_mtime = min(path.stat().st_mtime for path in required)
    except OSError:
        return True
    if max_age_seconds >= 0 and time.time() - audit_mtime > float(max_age_seconds):
        return True

    authority_candidates = [
        root / "project.control.json", root / "Cargo.toml", root / "CMakeLists.txt",
        root / "pyproject.toml", root / "requirements.txt", root / "package.json",
        root / "build.gradle", root / "settings.gradle", root / "gradlew", root / "gradlew.bat",
    ]
    control = root / "tools" / "control"
    if control.is_dir():
        try:
            authority_candidates.extend(path for path in control.iterdir() if path.is_file() and path.suffix.casefold() in {".py", ".ps1", ".json", ".toml"})
        except OSError:
            pass
    for path in authority_candidates:
        try:
            if path.is_file() and path.stat().st_mtime > audit_mtime:
                return True
        except OSError:
            return True
    return False


def write_handoffs(root: Path, *, deep: bool = False) -> dict[str, Any]:
    data = audit(root, deep=deep)
    project_id = str(data["project"]["id"])
    target = _audit_target(root, project_id)
    target.mkdir(parents=True, exist_ok=True)

    audit_path = target / "PROJECT_AUDIT.json"
    support_path = target / "FORGEPY_SUPPORT_HANDOFF.md"
    project_path = target / "PROJECT_INTEGRATION_HANDOFF.md"
    intelligence_path = target / "PROJECT_INTELLIGENCE.json"

    # Handoffs are being written now; promote grade with the handoff-current condition.
    data["protocol"] = integration_grade(data["capabilities"], audit_current=True, handoffs_current=True)
    audit_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    support_path.write_text(_forgepy_handoff(data), encoding="utf-8")
    project_path.write_text(_project_handoff(data), encoding="utf-8")

    intelligence = {
        "schema": "forgepy.project-intelligence.v1",
        "project": data["project"],
        "integration": data["protocol"],
        "provider": data["provider"],
        "capabilities": data["capabilities"],
        "effectiveCapabilities": data.get("effectiveCapabilities", []),
        "source": data["source"],
        "toolchain": data["toolchain"],
        "updates": data["updates"],
        "capturedUtc": data["capturedUtc"],
    }
    intelligence_path.write_text(json.dumps(intelligence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "audit": data,
        "auditPath": str(audit_path),
        "forgePySupportHandoff": str(support_path),
        "projectIntegrationHandoff": str(project_path),
        "projectIntelligence": str(intelligence_path),
    }
