#!/usr/bin/env python3
"""Canonical ForgePY branding and desktop icon authority."""
from __future__ import annotations
from pathlib import Path
from typing import Any

PRODUCT_NAME = "ForgePY"
APP_ROOT = Path(__file__).resolve().parents[1]
BRANDING_ROOT = APP_ROOT / "assets" / "branding"
ICON_PNG = BRANDING_ROOT / "ForgePY.png"
ICON_ICO = BRANDING_ROOT / "ForgePY.ico"


def apply_window_icon(window: Any) -> bool:
    """Apply the canonical icon to a Tk/Toplevel window without making launch fragile."""
    applied = False
    try:
        if ICON_ICO.is_file():
            window.iconbitmap(default=str(ICON_ICO))
            applied = True
    except Exception:
        pass
    try:
        if ICON_PNG.is_file():
            photo = window.tk.call("image", "create", "photo", "-file", str(ICON_PNG))
            window.tk.call("wm", "iconphoto", window._w, True, photo)
            # Keep Tcl image name alive for the window lifetime.
            window._forgepy_icon_photo = photo
            applied = True
    except Exception:
        pass
    return applied

__all__ = ["PRODUCT_NAME", "APP_ROOT", "BRANDING_ROOT", "ICON_PNG", "ICON_ICO", "apply_window_icon"]
