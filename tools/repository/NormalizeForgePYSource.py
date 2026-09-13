#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

NORMALIZER_VERSION = "FORGEPY-SOURCE-NORMALIZER-1.0-F741"
LEGACY_ROOT_NAMES = (
    "ForgePY",
    "overwrite_source",
    "README_FIRST.txt",
    "REPAIR_MANIFEST.json",
    "RUN_REPAIR.cmd",
    "OVERWRITE_SOURCE_MANIFEST.json",
    "OVERWRITE_SOURCE_README.txt",
    "PublishForgePYRepository.cmd",
    "PublishForgePYRepository.ps1",
    "ForgePYDebug.cmd",
)


def inspect(root: Path) -> dict[str, object]:
    root = root.expanduser().resolve()
    legacy = [name for name in LEGACY_ROOT_NAMES if (root / name).exists()]
    caches = [p for p in root.rglob("__pycache__") if ".git" not in p.parts]
    bytecode = [p for p in root.rglob("*.py[co]") if ".git" not in p.parts]
    return {
        "schema": "forgepy.source-normalization.v1",
        "version": NORMALIZER_VERSION,
        "root": str(root),
        "canonicalApp": str(root / "app"),
        "canonicalOk": (root / "app" / "ForgePYBootstrap.py").is_file() and (root / "app" / "ForgeGui.py").is_file(),
        "legacyRootEntries": legacy,
        "pythonCacheDirectories": len(caches),
        "pythonBytecodeFiles": len(bytecode),
        "clean": not legacy and not caches and not bytecode,
    }


def apply(root: Path) -> dict[str, object]:
    root = root.expanduser().resolve()
    before = inspect(root)
    if not before["canonicalOk"]:
        raise RuntimeError("refusing source cleanup: canonical app/ authority is incomplete")
    removed: list[str] = []
    for name in LEGACY_ROOT_NAMES:
        path = root / name
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(name)
    for path in sorted((p for p in root.rglob("__pycache__") if ".git" not in p.parts), key=lambda p: len(p.parts), reverse=True):
        if path.exists():
            shutil.rmtree(path)
    for pattern in ("*.pyc", "*.pyo"):
        for path in root.rglob(pattern):
            if ".git" not in path.parts and path.is_file():
                path.unlink()
    after = inspect(root)
    after["removed"] = removed
    return after


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit or explicitly normalize a ForgePY source checkout.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--apply", action="store_true", help="Remove only known legacy duplicate/repair root entries and Python caches.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    result = apply(root) if args.apply else inspect(root)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        state = "CLEAN" if result.get("clean") else "NEEDS NORMALIZATION"
        print(f"[{ 'PASS' if result.get('clean') else 'WARN' }] ForgePY source: {state}")
        print(f"Root: {result.get('root')}")
        if result.get("legacyRootEntries"):
            print("Legacy root entries: " + ", ".join(result["legacyRootEntries"]))
        print(f"Python cache directories: {result.get('pythonCacheDirectories', 0)}")
        print(f"Python bytecode files: {result.get('pythonBytecodeFiles', 0)}")
        if result.get("removed"):
            print("Removed: " + ", ".join(result["removed"]))
    return 0 if result.get("clean") else 1


if __name__ == "__main__":
    raise SystemExit(main())
