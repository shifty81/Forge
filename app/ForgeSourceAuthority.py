#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_AUTHORITY_VERSION = "FORGEPY-SOURCE-AUTHORITY-2.0-F741"
SCHEMA = "forgepy.source-authority.v1"
CANONICAL_APP_FILES = ("ForgePYBootstrap.py", "ForgeGui.py", "ForgePYVersion.py")
LEGACY_MIRROR = "ForgePY"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def matrix(*, working: str = "", head: str = "", green: str = "", forgegit: str = "", github: str = "") -> dict[str, Any]:
    refs = {"working": working, "head": head, "green": green, "forgegit": forgegit, "github": github}
    present = {k: v for k, v in refs.items() if v}
    unique = set(present.values())
    if not present:
        state = "UNKNOWN"
    elif len(unique) == 1:
        state = "SYNC"
    else:
        state = "DIVERGED"
    return {"schema": SCHEMA, "version": SOURCE_AUTHORITY_VERSION, "state": state, "refs": refs, "distinct": len(unique)}


def safe_branch_name(name: str) -> str:
    value = "-".join(str(name).strip().split())
    for bad in ("..", "~", "^", ":", "?", "*", "[", "\\", " "):
        value = value.replace(bad, "-")
    value = value.strip("/.-")
    if not value:
        raise ValueError("branch name is empty")
    return value


def _launcher_targets_legacy_mirror(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace").replace("/", "\\").casefold()
    except OSError:
        return False
    # Explicit nested source routing is forbidden. Compatibility launchers may still be named Forge.*,
    # but they must route into root app/, never ForgePY/app/.
    return "forgepy\\app\\" in text or "%forgepy_home%forgepy\\app\\" in text


def audit(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    app = root / "app"
    mirror = root / LEGACY_MIRROR
    errors: list[str] = []
    warnings: list[str] = []

    missing = [name for name in CANONICAL_APP_FILES if not (app / name).is_file()]
    if missing:
        errors.append("canonical app source missing: " + ", ".join(missing))

    launcher_rows: list[dict[str, Any]] = []
    for name in ("ForgePY.cmd", "ForgePY.vbs", "Forge.cmd", "Forge.vbs"):
        path = root / name
        if not path.is_file():
            if name.startswith("ForgePY"):
                errors.append(f"canonical launcher missing: {name}")
            continue
        legacy = _launcher_targets_legacy_mirror(path)
        launcher_rows.append({"path": name, "legacyMirrorTarget": legacy})
        if legacy:
            errors.append(f"launcher targets legacy nested source tree: {name}")

    overlap = identical = divergent = 0
    mirror_state = "absent"
    mirror_rows: list[dict[str, Any]] = []
    if mirror.is_dir():
        for name in CANONICAL_APP_FILES:
            left = app / name
            right = mirror / "app" / name
            if not left.is_file() or not right.is_file():
                continue
            overlap += 1
            try:
                same = left.stat().st_size == right.stat().st_size and _sha(left) == _sha(right)
            except OSError:
                same = False
            identical += int(same)
            divergent += int(not same)
            mirror_rows.append({"path": f"app/{name}", "same": same})
        mirror_state = "diverged" if divergent else ("identical" if overlap else "present")
        warnings.append(
            f"legacy nested ForgePY/ mirror present ({mirror_state}); root app/ remains the only source authority"
        )

    return {
        "schema": SCHEMA,
        "version": SOURCE_AUTHORITY_VERSION,
        "root": str(root),
        "canonicalApp": str(app),
        "legacyMirror": str(mirror),
        "mirrorState": mirror_state,
        "mirrorOverlap": overlap,
        "mirrorIdentical": identical,
        "mirrorDivergent": divergent,
        "mirrorFiles": mirror_rows,
        "launchers": launcher_rows,
        "warnings": warnings,
        "errors": errors,
        "ok": not errors,
        "policy": "root app/ is authoritative; nested ForgePY/ is legacy/reference-only and must not be a launcher or release authority",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit ForgePY canonical source authority")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)
    result = audit(Path(ns.root))
    if ns.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"[{'PASS' if result['ok'] else 'FAIL'}] ForgePY source authority: {result['canonicalApp']}")
        for warning in result["warnings"]:
            print(f"[WARN] {warning}")
        for error in result["errors"]:
            print(f"[FAIL] {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
