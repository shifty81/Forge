#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _git(root: Path, *args: str) -> str:
    try:
        cp = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=5, check=False,
            creationflags=(int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0),
        )
        return cp.stdout.strip() if cp.returncode == 0 else ""
    except Exception:
        return ""


def build_identity(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    identity: dict[str, Any] = {
        "schema": "forge.build.identity.v1",
        "root": str(root),
        "capturedUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": root.name,
        "projectName": root.name,
        "projectVersion": "",
        "projectBuild": "",
        "certifiedProjectVersion": "",
        "certifiedProjectBuild": "",
        "candidateProjectVersion": "",
        "candidateProjectBuild": "",
        "identityPhase": "certified",
        "gitCommit": _git(root, "rev-parse", "HEAD"),
        "gitBranch": _git(root, "branch", "--show-current"),
        "greenId": "",
        "greenGitCommit": "",
        "attestation": "",
    }
    contract = _read_json(root / "project.control.json")
    project = contract.get("project") if isinstance(contract.get("project"), dict) else {}
    if project:
        identity["projectId"] = str(project.get("id") or identity["projectId"])
        identity["projectName"] = str(project.get("name") or identity["projectName"])

        certified_version = str(project.get("version") or project.get("release") or "")
        certified_build = str(project.get("build") or project.get("buildId") or "")
        candidate_version = str(project.get("candidateVersion") or "")
        candidate_build = str(project.get("candidateBuild") or "")

        identity["certifiedProjectVersion"] = certified_version
        identity["certifiedProjectBuild"] = certified_build
        identity["candidateProjectVersion"] = candidate_version
        identity["candidateProjectBuild"] = candidate_build
        identity["identityPhase"] = "candidate" if (candidate_version or candidate_build) else "certified"

        # Routing and patch preconditions must follow the source tree that is actually
        # present.  ForgePY keeps the last promoted GREEN identity alongside a newer
        # candidate identity; using the certified donor build here made every normal
        # F7xx -> F7xx+1 update look incompatible even though the GUI correctly showed
        # the candidate build.
        identity["projectVersion"] = candidate_version or certified_version
        identity["projectBuild"] = candidate_build or certified_build

    # Forge's legacy version module represents the last promoted/certified donor.
    # Preserve it as certified evidence, but never overwrite an explicit candidate
    # identity from project.control.json. VaultVersion remains a compatibility fallback
    # for installations created before the Forge rename.
    for version_name in ("ForgePYVersion.py", "ForgeVersion.py", "VaultVersion.py"):
        version_file = root / "app" / version_name
        if not version_file.is_file():
            continue
        ns: dict[str, Any] = {}
        try:
            import sys
            app_path = str((root / "app").resolve())
            added = app_path not in sys.path
            if added:
                sys.path.insert(0, app_path)
            try:
                exec(compile(version_file.read_text(encoding="utf-8"), version_name, "exec"), {}, ns)
            finally:
                if added and sys.path and sys.path[0] == app_path:
                    sys.path.pop(0)
            legacy_version = str(ns.get("VERSION") or "")
            legacy_build = str(ns.get("BUILD") or "")
            if legacy_version and not identity.get("certifiedProjectVersion"):
                identity["certifiedProjectVersion"] = legacy_version
            if legacy_build and not identity.get("certifiedProjectBuild"):
                identity["certifiedProjectBuild"] = legacy_build
            if not identity.get("projectVersion"):
                identity["projectVersion"] = legacy_version
            if not identity.get("projectBuild"):
                identity["projectBuild"] = legacy_build
            if legacy_version or legacy_build:
                break
        except Exception:
            continue

    for marker in (
        root / "artifacts" / "green-gate.json",
        root / "artifacts" / "green_gate.json",
        root / ".project-control" / "green-gate.json",
        root / ".project_control" / "green-gate.json",
    ):
        data = _read_json(marker)
        if not data:
            continue
        identity["greenId"] = str(data.get("gateId") or data.get("greenId") or data.get("id") or data.get("local") or "")
        identity["greenGitCommit"] = str(data.get("gitHead") or data.get("gitCommit") or data.get("commit") or "")
        break

    candidates = list((root / "artifacts").glob("**/*attestation*.json")) if (root / "artifacts").is_dir() else []
    if candidates:
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        identity["attestation"] = str(latest)
        data = _read_json(latest)
        if not identity["projectBuild"]:
            identity["projectBuild"] = str(data.get("buildId") or data.get("build") or "")
        if not identity["projectVersion"]:
            identity["projectVersion"] = str(data.get("version") or "")
    return identity


def verify_manifest_preconditions(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    identity = build_identity(root)
    declared: dict[str, Any] = {}
    for key in ("requires", "preconditions", "targetBuild"):
        value = manifest.get(key)
        if isinstance(value, dict):
            declared.update(value)

    # Accept a compact set of stable aliases without inventing project-specific semantics.
    checks = (
        (("gitCommit", "gitHead", "commit", "sourceCommit"), "gitCommit"),
        (("projectVersion", "version", "targetVersion"), "projectVersion"),
        (("projectBuild", "build", "buildId", "baseline"), "projectBuild"),
        (("greenId", "gateId", "green"), "greenId"),
    )
    mismatches: list[dict[str, str]] = []
    matched: list[dict[str, str]] = []
    for aliases, identity_key in checks:
        expected = ""
        source_key = ""
        for alias in aliases:
            if alias in declared and declared.get(alias) not in (None, ""):
                expected = str(declared.get(alias)).strip()
                source_key = alias
                break
        if not expected:
            continue
        actual = str(identity.get(identity_key) or "").strip()
        # Git declarations may intentionally use an unambiguous short prefix.
        ok = actual == expected or (identity_key == "gitCommit" and actual.lower().startswith(expected.lower()))
        row = {"field": source_key, "expected": expected, "actual": actual}
        (matched if ok else mismatches).append(row)
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "identity": identity,
        "matched": matched,
        "mismatches": mismatches,
        "declared": declared,
    }


__all__ = ["build_identity", "verify_manifest_preconditions"]
