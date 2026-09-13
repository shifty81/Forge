#!/usr/bin/env python3
"""ForgePY Project Provider Protocol v1.

Projects remain independently buildable.  This module defines the semantic contract
ForgePY consumes when a project provides a native/declared adapter.  Discovery remains
fallback-only and must not invent domain-specific operations.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

PROTOCOL_SCHEMA = "forgepy.provider.v1"
PROTOCOL_VERSION = 1
STANDARD_COMMANDS = (
    "project.status",
    "gate.full",
    "gate.quick",
    "build.default",
    "build.release",
    "test.default",
    "run.default",
    "run.editor",
    "debug.bundle",
    "doctor.default",
    "package.default",
)
STANDARD_CATEGORIES = (
    "Build & Certification",
    "Run & Debug",
    "Content & Assets",
    "World & Data",
    "Packaging & Release",
    "Maintenance",
    "Development",
    "Advanced",
)
VALID_RISKS = {"read-only", "writes-project", "destructive", "network", "release"}


@dataclass(frozen=True)
class ProviderCommandV1:
    command_id: str
    label: str
    category: str
    provider_key: str
    description: str = ""
    risk: str = "read-only"
    requires_clean_tree: bool = False
    cancellable: bool = True
    tool_requirements: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["tool_requirements"] = list(self.tool_requirements)
        return row


def validate_command(row: ProviderCommandV1 | dict[str, Any]) -> list[str]:
    data = row.to_dict() if isinstance(row, ProviderCommandV1) else dict(row)
    errors: list[str] = []
    cid = str(data.get("command_id") or data.get("id") or "").strip()
    if not cid or "." not in cid:
        errors.append("command id must be a stable dotted semantic identifier")
    if not str(data.get("label") or "").strip():
        errors.append(f"{cid or '<command>'}: label is required")
    category = str(data.get("category") or "").strip()
    if category not in STANDARD_CATEGORIES:
        errors.append(f"{cid or '<command>'}: unsupported category {category!r}")
    risk = str(data.get("risk") or "read-only").strip().casefold()
    if risk not in VALID_RISKS:
        errors.append(f"{cid or '<command>'}: unsupported risk {risk!r}")
    if not str(data.get("provider_key") or data.get("providerKey") or "").strip():
        errors.append(f"{cid or '<command>'}: provider key is required")
    return errors


def validate_descriptor(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if str(data.get("schema") or "") != PROTOCOL_SCHEMA:
        errors.append(f"schema must be {PROTOCOL_SCHEMA}")
    if int(data.get("protocolVersion") or 0) != PROTOCOL_VERSION:
        errors.append(f"protocolVersion must be {PROTOCOL_VERSION}")
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    if not str(project.get("id") or "").strip(): errors.append("project.id is required")
    if not str(project.get("name") or "").strip(): errors.append("project.name is required")
    commands = data.get("commands")
    if not isinstance(commands, list):
        errors.append("commands must be an array")
        return errors
    seen: set[str] = set()
    for index, row in enumerate(commands):
        if not isinstance(row, dict):
            errors.append(f"commands[{index}] must be an object"); continue
        cid = str(row.get("command_id") or row.get("id") or "").casefold()
        if cid in seen: errors.append(f"duplicate command id: {cid}")
        seen.add(cid)
        errors.extend(validate_command(row))
    return errors


def compatibility_state(data: dict[str, Any]) -> str:
    version = int(data.get("protocolVersion") or 0)
    if version == PROTOCOL_VERSION:
        return "CURRENT"
    if version < PROTOCOL_VERSION:
        return "UPGRADE REQUIRED"
    return "TOO NEW"


def compatibility_report(data: dict[str, Any]) -> dict[str, Any]:
    """Return one deterministic provider/adaptor compatibility result for UI and gates."""
    errors = validate_descriptor(data)
    state = compatibility_state(data)
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocolVersion": PROTOCOL_VERSION,
        "state": state if not errors else ("INVALID" if state == "CURRENT" else state),
        "valid": not errors and state == "CURRENT",
        "errors": errors,
        "projectId": str(((data.get("project") or {}) if isinstance(data.get("project"), dict) else {}).get("id") or ""),
        "commandCount": len(data.get("commands") or []) if isinstance(data.get("commands"), list) else 0,
    }


def verified_operation_states() -> tuple[str, ...]:
    """Only audited/certified project tools may become persistent Operations buttons."""
    return ("VERIFIED", "CERTIFIED")


def descriptor(project_id: str, project_name: str, commands: Iterable[ProviderCommandV1], *, adapter: str = "declared") -> dict[str, Any]:
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocolVersion": PROTOCOL_VERSION,
        "project": {"id": str(project_id), "name": str(project_name)},
        "adapter": str(adapter),
        "commands": [row.to_dict() for row in commands],
    }


def project_reference_files() -> dict[str, str]:
    """Small project-local compatibility kit text payloads for audited repositories."""
    return {
        ".forgepy/forgepy-version.lock": "ProviderProtocol=1\nPatchManifest=1\nCompatibilityKit=1\n",
        ".forgepy/README.md": (
            "# ForgePY Compatibility Kit v1\n\n"
            "This directory describes how this project exposes real build/run/test/tool operations to the standalone ForgePY application. "
            "ForgePY is not vendored as a runtime/build dependency. The project remains independently buildable and certifiable.\n"
        ),
    }
