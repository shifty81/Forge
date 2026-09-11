#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

FORGE_PROJECT_SCHEMA = "forge.project.v1"
FORGE_PATCH_SCHEMA = "forge.patch.v1"
INCOMING_PATCH_NAME = "incoming.patch"

CANONICAL_OPERATION_PREFIXES = (
    "project.", "gate.", "build.", "test.", "run.", "git.", "source.",
    "patch.", "updates.", "doctor.", "diagnostics.", "package.", "assets.",
    "tooling.", "recovery.", "artifacts.", "dependencies.", "audit.",
)


def validate_project_contract(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("project contract root must be an object")
    schema = str(data.get("schema") or "").strip()
    if schema != FORGE_PROJECT_SCHEMA:
        raise ValueError(f"expected schema {FORGE_PROJECT_SCHEMA!r}; got {schema or '<missing>'!r}")
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    for key in ("id", "name", "kind"):
        if not str(project.get(key) or "").strip():
            raise ValueError(f"project.{key} is required")

    commands = data.get("commands") or []
    if not isinstance(commands, list):
        raise ValueError("commands must be an array")
    keys: set[str] = set()
    for index, item in enumerate(commands):
        if not isinstance(item, dict):
            raise ValueError(f"commands[{index}] must be an object")
        key = str(item.get("key") or "").strip()
        if not key:
            raise ValueError(f"commands[{index}].key is required")
        if key in keys:
            raise ValueError(f"duplicate command key: {key}")
        keys.add(key)

    updates = data.get("updates") if isinstance(data.get("updates"), dict) else {}
    incoming = str(updates.get("incoming") or INCOMING_PATCH_NAME).strip()
    if incoming.casefold() != INCOMING_PATCH_NAME:
        raise ValueError(f"updates.incoming must be the reserved filename {INCOMING_PATCH_NAME}")
    patch_schema = str(updates.get("patchSchema") or FORGE_PATCH_SCHEMA).strip()
    if patch_schema != FORGE_PATCH_SCHEMA:
        raise ValueError(f"updates.patchSchema must be {FORGE_PATCH_SCHEMA}")
    if updates and updates.get("downloadsAutoQueue") not in (None, False):
        raise ValueError("updates.downloadsAutoQueue must be false")

    return {
        "schema": schema,
        "projectId": str(project.get("id")),
        "commandCount": len(commands),
        "incoming": incoming,
        "patchSchema": patch_schema,
    }


def validate_patch_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("patch manifest root must be an object")
    schema = str(manifest.get("schema") or "").strip()
    if schema != FORGE_PATCH_SCHEMA:
        raise ValueError(f"expected patch schema {FORGE_PATCH_SCHEMA!r}; got {schema or '<missing>'!r}")
    for key in ("patchId", "project", "createdUtc"):
        if not str(manifest.get(key) or "").strip():
            raise ValueError(f"{key} is required")
    declared = {}
    for key in ("requires", "preconditions", "targetBuild"):
        value = manifest.get(key)
        if isinstance(value, dict):
            declared.update(value)
    if not declared:
        raise ValueError("patch must declare target build/source preconditions")
    return {"schema": schema, "patchId": str(manifest.get("patchId")), "project": str(manifest.get("project"))}


__all__ = [
    "FORGE_PROJECT_SCHEMA", "FORGE_PATCH_SCHEMA", "INCOMING_PATCH_NAME",
    "CANONICAL_OPERATION_PREFIXES", "validate_project_contract", "validate_patch_contract",
]
