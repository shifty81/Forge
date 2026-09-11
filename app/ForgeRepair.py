#!/usr/bin/env python3
from __future__ import annotations
import json, hashlib
from pathlib import Path
from ForgeVaultBootstrap import ensure_layout

REPAIR_VERSION='FORGEPY-REPAIR-0.1'
APP_ROOT=Path(__file__).resolve().parents[1]

def diagnose() -> dict:
    issues=[]
    manifest=APP_ROOT/'FORGEPY_PACKAGE_MANIFEST.json'
    if not manifest.is_file(): issues.append('package manifest missing')
    for rel in ('app/ForgePYStandalone.py','app/ForgeGui.py','project.control.json'):
        if not (APP_ROOT/rel).is_file(): issues.append(f'missing {rel}')
    try: ensure_layout()
    except Exception as exc: issues.append(f'vault layout: {exc}')
    return {'ok':not issues,'issues':issues}

def repair_safe() -> dict:
    # Repair mode is deliberately conservative: initialize machine-local structure.
    # Application source repair is performed from a verified release package/updater.
    layout=ensure_layout(); return {'ok':True,'layout':layout,'sourceModified':False}
