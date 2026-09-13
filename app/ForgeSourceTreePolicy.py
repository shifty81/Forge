#!/usr/bin/env python3
from __future__ import annotations
import hashlib, os
from pathlib import Path
from typing import Any
from ForgePackagePolicy import is_governed

SOURCE_TREE_POLICY_VERSION = "FORGEPY-SOURCE-TREE-POLICY-1.1-F620"
LEGACY_MIRROR = "ForgePY"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def report(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    mirror_root = root / LEGACY_MIRROR
    overlaps: list[dict[str, Any]] = []
    divergent = identical = 0
    if mirror_root.is_dir():
        for current, dirs, files in os.walk(mirror_root):
            dirs[:] = [d for d in dirs if d.casefold() not in {".git", "__pycache__", "logs", "artifacts", "dist", "build", "target"}]
            current_path = Path(current)
            for name in files:
                right = current_path / name
                try:
                    rel_inside = right.relative_to(mirror_root)
                except ValueError:
                    continue
                left = root / rel_inside
                if not left.is_file() or not is_governed(rel_inside.as_posix()):
                    continue
                try:
                    same = left.stat().st_size == right.stat().st_size and _sha(left) == _sha(right)
                except OSError:
                    same = False
                identical += int(same)
                divergent += int(not same)
                overlaps.append({"path": rel_inside.as_posix(), "same": same})
    return {
        "schema": "forgepy.source-tree-authority.v1",
        "version": SOURCE_TREE_POLICY_VERSION,
        "canonical": str(root / "app"),
        "legacyMirror": str(mirror_root),
        "legacyMirrorPresent": mirror_root.is_dir(),
        "overlapCount": len(overlaps),
        "identicalCount": identical,
        "divergentCount": divergent,
        "overlaps": overlaps,
        "policy": "root tree/app is authoritative; top-level ForgePY/ is compatibility/reference only and excluded from governed release/GREEN content",
    }
