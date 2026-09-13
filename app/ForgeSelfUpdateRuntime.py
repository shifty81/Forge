#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

SELF_UPDATE_RUNTIME_VERSION = "FORGEPY-SELF-UPDATE-RUNTIME-2.0-F740"

LEGACY_REASON = (
    "Legacy single-executable self-update is disabled. ForgePY is a Nuitka standalone/onedir "
    "application; replacing only ForgePY.exe can create a mixed-version install. "
    "Use ForgeSelfMaintenance with a validated .forgeupdate application-image bundle."
)


def stage(plan: Any, expected_sha256: str) -> dict[str, Any]:
    raise RuntimeError(LEGACY_REASON)


def promotion_plan(plan: Any) -> dict[str, Any]:
    return {
        "schema": "forgepy.self-update-promotion.v2",
        "version": SELF_UPDATE_RUNTIME_VERSION,
        "supported": False,
        "reason": LEGACY_REASON,
        "replacement": "ForgeSelfMaintenance",
        "transport": ".forgeupdate",
    }


def compatibility_status() -> dict[str, Any]:
    return {
        "version": SELF_UPDATE_RUNTIME_VERSION,
        "legacySingleExe": False,
        "directoryTransaction": True,
        "replacement": "ForgeSelfMaintenance",
        "reason": LEGACY_REASON,
    }
