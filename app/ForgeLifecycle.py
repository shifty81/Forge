#!/usr/bin/env python3
from __future__ import annotations
import time
from dataclasses import dataclass, asdict
from typing import Callable, Any

LIFECYCLE_VERSION = "FORGEPY-LIFECYCLE-1.0"

@dataclass(frozen=True)
class Phase:
    key: str
    label: str
    timeout_seconds: float = 10.0
    required: bool = True

DEFAULT_PHASES = (
    Phase("runtime", "Runtime integrity", 3),
    Phase("package", "Package manifest", 5),
    Phase("settings", "Settings", 3),
    Phase("vault", "Vault configuration", 5),
    Phase("registry", "Project registry", 5),
    Phase("project", "Active project", 8, False),
)

def run(phases, handlers: dict[str, Callable[[], Any]]) -> dict[str, Any]:
    rows = []
    ok = True
    for phase in phases:
        started = time.monotonic()
        try:
            value = handlers.get(phase.key, lambda: None)()
            elapsed = time.monotonic() - started
            if elapsed > phase.timeout_seconds:
                raise TimeoutError(f"{phase.label} exceeded {phase.timeout_seconds:.1f}s")
            rows.append({**asdict(phase), "state": "PASS", "elapsedMs": round(elapsed*1000, 1), "value": value})
        except Exception as exc:
            elapsed = time.monotonic() - started
            rows.append({**asdict(phase), "state": "FAIL" if phase.required else "WARN", "elapsedMs": round(elapsed*1000, 1), "error": str(exc)})
            if phase.required:
                ok = False
    return {"schema": "forgepy.lifecycle.v1", "version": LIFECYCLE_VERSION, "ok": ok, "phases": rows}
