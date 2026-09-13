#!/usr/bin/env python3
from __future__ import annotations

from typing import Any
from ForgeProjectProtocol import normalize_key

AVAILABILITY_VERSION = "FORGEPY-COMMAND-AVAILABILITY-2.0-F463"


def matrix(commands: list[dict[str, Any]], capabilities: set[str], tool_states: dict[str, str] | None = None) -> list[dict[str, Any]]:
    tool_states = tool_states or {}
    canonical_caps = {normalize_key(x) for x in capabilities}
    rows: list[dict[str, Any]] = []
    for command in commands:
        row = dict(command)
        key = str(row.get("key") or row.get("command") or "")
        required = {normalize_key(str(x)) for x in (row.get("requires") or [])}
        missing = sorted(required - canonical_caps)
        tool = str(row.get("toolId") or "")
        if tool and tool_states.get(tool) not in {"READY", "EXECUTABLE", "VERIFIED"}:
            missing.append("tool:" + tool)
        row["canonicalKey"] = normalize_key(key)
        row["available"] = not missing
        row["missing"] = missing
        rows.append(row)
    return rows
