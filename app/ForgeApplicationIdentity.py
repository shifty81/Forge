#!/usr/bin/env python3
from __future__ import annotations
import re
from typing import Any

IDENTITY_VERSION = "FORGEPY-APPLICATION-IDENTITY-2.1-F797"
RELEASE_LINE = "0.5.0"
CANDIDATE_REVISION = 797
DISPLAY_VERSION = f"{RELEASE_LINE}-candidate.{CANDIDATE_REVISION}"
DISPLAY_BUILD = f"FORGEPY-F{CANDIDATE_REVISION}"
CHANNEL = "candidate"

def current() -> dict[str, Any]:
    try:
        from ForgePYVersion import VERSION as certified_base, BUILD as certified_build
    except Exception:
        certified_base, certified_build = "", ""
    return {
        "schema": "forgepy.application-identity.v1",
        "version": IDENTITY_VERSION,
        "product": "ForgePY",
        "displayVersion": DISPLAY_VERSION,
        "displayBuild": DISPLAY_BUILD,
        "channel": CHANNEL,
        "certifiedBaseVersion": certified_base,
        "certifiedBaseBuild": certified_build,
        "candidateRevision": CANDIDATE_REVISION,
    }

def normalize_label_text(text: str) -> str:
    value = str(text or "")
    if not value:
        return value
    low = value.casefold()
    if "forgepy" in low and ("candidate" in low or "0.4.415-f60r415" in low):
        if low.strip().startswith("v") and "active" in low:
            return f"v{DISPLAY_VERSION}  ACTIVE"
        if "candidate" in low:
            value = re.sub(
                r"(?:0\.4\.415-F60R415|0\.5\.0-candidate\.\d+)?\s*[·•-]?\s*F\d+\s+candidate",
                f"{DISPLAY_VERSION} · {DISPLAY_BUILD}",
                value,
                flags=re.I,
            )
            return value.replace("ForgePY  ·", "ForgePY ·").replace("ForgePY0.5", "ForgePY 0.5")
    if re.fullmatch(r"v?0\.4\.415-F60R415(?:\s+ACTIVE)?", value, re.I):
        return f"v{DISPLAY_VERSION}  ACTIVE" if "active" in low else DISPLAY_VERSION
    if re.fullmatch(r"F\d+\s+candidate", value, re.I):
        return f"F{CANDIDATE_REVISION} candidate"
    return value

def normalize_gui(gui: Any, *, full_scan: bool = False) -> None:
    """Normalize visible application identity without repeatedly walking the whole GUI."""
    if getattr(gui, "_forge_identity_full_normalized", False) and not full_scan:
        return
    try:
        from ForgeUnifiedWorkflow import _walk_widgets, _widget_text
    except Exception:
        return
    for widget in _walk_widgets(gui.window):
        text = _widget_text(widget)
        updated = normalize_label_text(text)
        if updated != text:
            try:
                widget.configure(text=updated)
            except Exception:
                pass
    gui._forge_identity_full_normalized = True
