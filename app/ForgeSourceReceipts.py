#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ForgePYPaths import ensure_artifact_project_tree

RECEIPT_VERSION = "FORGEPY-SOURCE-RECEIPT-0.1"


def write_receipt(project_id: str, operation: str, payload: dict[str, Any]) -> Path:
    root = ensure_artifact_project_tree(project_id)["reports"] / "source-control" / "receipts"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = root / f"{stamp}-{operation}.json"
    body = {
        "schema": "forgepy.source_control_receipt.v1",
        "version": RECEIPT_VERSION,
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": project_id,
        "operation": operation,
        **dict(payload),
    }
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(body, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush(); os.fsync(fh.fileno())
        os.replace(temp_name, path)
    finally:
        try: os.unlink(temp_name)
        except FileNotFoundError: pass
    return path
