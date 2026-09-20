#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path: sys.path.insert(0, str(APP))
from ForgePYVersion import VERSION, BUILD
from ForgePackagePolicy import is_governed

OUTPUT = ROOT / "FORGEPY_PACKAGE_MANIFEST.json"
EXCLUDED_NAMES = {"FORGEPY_PACKAGE_MANIFEST.json", "FORGE_PACKAGE_MANIFEST.json", "VAULT_PACKAGE_MANIFEST.json"}
PRUNE_ANYWHERE = {".git", "__pycache__", "node_modules", "target", "build", "builds", "bin", "obj", ".venv", "venv", ".cache", ".pytest_cache", ".idea", ".vs"}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _files():
    rows = []
    for current, dirs, files in os.walk(ROOT):
        current_path = Path(current)
        kept = []
        for d in dirs:
            rel = (current_path / d).relative_to(ROOT).as_posix()
            # Rust's src/bin holds declared source targets (ForgeTool), not build
            # output. Never silently omit it from a supposedly complete rollup.
            rust_bin_source = rel == "native/forge-rs/src/bin"
            if (d.casefold() in PRUNE_ANYWHERE and not rust_bin_source) or not is_governed(rel):
                continue
            kept.append(d)
        dirs[:] = kept
        for name in files:
            path = current_path / name
            rel = path.relative_to(ROOT)
            if name in EXCLUDED_NAMES or not is_governed(rel.as_posix()):
                continue
            rows.append({"path": rel.as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path)})
    rows.sort(key=lambda row: row["path"].casefold())
    return rows


def main() -> int:
    rows = _files()
    generated = datetime.now(timezone.utc).isoformat()
    try:
        old = json.loads(OUTPUT.read_text(encoding="utf-8-sig")) if OUTPUT.is_file() else {}
        if old.get("forgePyVersion") == VERSION and old.get("forgePyBuild") == BUILD and old.get("files") == rows:
            generated = str(old.get("generatedUtc") or generated)
    except Exception:
        pass
    payload = {"schema": "forgepy.package.manifest.v1", "forgePyVersion": VERSION, "forgePyBuild": BUILD, "generatedUtc": generated, "fileCount": len(rows), "files": rows}
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    previous = OUTPUT.read_text(encoding="utf-8-sig") if OUTPUT.is_file() else ""
    if encoded != previous:
        OUTPUT.write_text(encoded, encoding="utf-8")
    print(f"[PASS] wrote {OUTPUT} with {len(rows)} canonical governed file(s)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
