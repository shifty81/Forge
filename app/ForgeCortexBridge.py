#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable

CORTEX_BRIDGE_VERSION = "FORGEPY-CORTEX-BRIDGE-1.0-F620"


def project_context(root: Path) -> dict[str, Any]:
    from ForgeProjectAudit import audit
    report = audit(root, deep=False)
    return {
        "schema": "forgepy.cortex-project-context.v1",
        "version": CORTEX_BRIDGE_VERSION,
        "project": report.get("project"),
        "protocol": report.get("protocol"),
        "source": report.get("source"),
        "tooling": report.get("tooling"),
        "artifacts": report.get("artifacts"),
        "updates": report.get("updates"),
    }


def run(
    runtime: Any,
    root: Path,
    canonical_command: str,
    *,
    extra: list[str] | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    return runtime.run_canonical(root, canonical_command, extra=extra, initiator="cortex", emit=emit)
