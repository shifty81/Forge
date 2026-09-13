#!/usr/bin/env python3
from __future__ import annotations

from typing import Any
from ForgeProjectProtocol import integration_grade

COMPLIANCE_VERSION = "FORGEPY-ADAPTER-COMPLIANCE-2.1-F566"


def audit(adapter: dict[str, Any]) -> dict[str, Any]:
    raw = adapter.get("capabilities") or {}
    capabilities = set(raw.keys()) if isinstance(raw, dict) else set(raw)
    grade = integration_grade(capabilities, audit_current=True, handoffs_current=True)
    return {
        "schema": "forgepy.adapter-compliance.v2",
        "version": COMPLIANCE_VERSION,
        "ok": not grade["standardMissing"],
        "grade": grade["grade"],
        "missingRecommended": grade["standardMissing"],
        "missingCertified": grade["certifiedMissing"],
        "capabilityCount": len(grade["capabilities"]),
        "capabilities": grade["capabilities"],
        "projectId": adapter.get("projectId"),
    }
