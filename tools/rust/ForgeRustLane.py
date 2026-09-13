#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

LANE_VERSION = "FORGEPY-RUST-LANE-0.5-F776"
NATIVE_PHASE = "SHADOW"


def _manifest(root: Path) -> Path:
    return root / "native" / "forge-rs" / "Cargo.toml"


def _binary(root: Path, *, release: bool = False) -> Path:
    profile = "release" if release else "debug"
    name = "ForgeNative.exe" if os.name == "nt" else "ForgeNative"
    return root / "native" / "forge-rs" / "target" / profile / name


def status(root: Path) -> dict[str, object]:
    cargo = shutil.which("cargo")
    rustc = shutil.which("rustc")
    manifest = _manifest(root)
    return {
        "schema": "forgepy.rust-lane.v2",
        "version": LANE_VERSION,
        "root": str(root),
        "manifest": str(manifest),
        "manifestReady": manifest.is_file(),
        "cargo": cargo or "",
        "cargoReady": bool(cargo),
        "rustc": rustc or "",
        "rustcReady": bool(rustc),
        "phase": NATIVE_PHASE,
        "authority": "python-forgepy",
        "takeoverReady": False,
        "evidence": str(root / ".forge" / "native" / "parity-latest.json"),
        "debugBinary": str(_binary(root)),
        "debugBinaryReady": _binary(root).is_file(),
    }


def _call(argv: Sequence[str], *, cwd: Path, timeout: int = 1800) -> int:
    print("[RUST] " + " ".join(str(x) for x in argv), flush=True)
    try:
        env = os.environ.copy()
        env.setdefault("FORGEPY_PYTHON", sys.executable)
        return int(subprocess.run(list(argv), cwd=cwd, check=False, timeout=timeout, env=env).returncode)
    except subprocess.TimeoutExpired:
        print(f"[FAIL] Rust command timed out after {timeout}s.", flush=True)
        return 124


def _cargo_command(root: Path, action: str) -> list[str] | None:
    row = status(root)
    cargo = str(row.get("cargo") or "")
    if not cargo:
        return None
    manifest = str(row["manifest"])
    mapping = {
        "check": [cargo, "check", "--manifest-path", manifest, "--all-targets"],
        "test": [cargo, "test", "--manifest-path", manifest, "--all-targets"],
        "build": [cargo, "build", "--manifest-path", manifest],
        "build-release": [cargo, "build", "--manifest-path", manifest, "--release"],
        "run": [cargo, "run", "--manifest-path", manifest, "--", "--root", str(root), "--gui"],
    }
    return mapping.get(action)


def _require_toolchain(root: Path) -> tuple[dict[str, object], int]:
    row = status(root)
    if not row["manifestReady"]:
        print("[FAIL] Rust successor manifest is missing.")
        return row, 2
    if not row["cargoReady"] or not row["rustcReady"]:
        print("[WARN] Rust successor lane is governed, but the Rust toolchain is not available on PATH.")
        print("[INFO] Python ForgePY remains the operational authority; native takeover remains blocked.")
        return row, 3
    return row, 0


def _run_binary(root: Path, *extra: str) -> int:
    binary = _binary(root)
    if not binary.is_file():
        rc = _call(_cargo_command(root, "build") or [], cwd=root)
        if rc:
            return rc
    return _call([str(binary), "--root", str(root), *extra], cwd=root, timeout=180)


def _launch_gui(root: Path) -> int:
    row, rc = _require_toolchain(root)
    if rc:
        return rc
    build = _cargo_command(root, "build")
    if not build:
        return 2
    rc = _call(build, cwd=root)
    if rc:
        return rc
    binary = _binary(root)
    env = os.environ.copy()
    env.setdefault("FORGEPY_PYTHON", sys.executable)
    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    try:
        subprocess.Popen([str(binary), "--root", str(root), "--gui"], cwd=str(root), env=env, creationflags=flags)
    except OSError as exc:
        print(f"[FAIL] Could not launch Forge Native GUI: {exc}", flush=True)
        return 2
    print(f"[PASS] Forge Native GUI launched: {binary}", flush=True)
    return 0


def gate(root: Path) -> int:
    row, rc = _require_toolchain(root)
    if rc:
        return rc
    print(f"[RUST] Forge Native {NATIVE_PHASE} certification starting.", flush=True)
    for action in ("check", "test", "build"):
        argv = _cargo_command(root, action)
        if not argv:
            return 2
        rc = _call(argv, cwd=root)
        if rc:
            print(f"[FAIL] Rust {NATIVE_PHASE} gate failed during {action}.", flush=True)
            return rc
    rc = _run_binary(root, "--self-test")
    if rc:
        print("[FAIL] Rust native self-test failed.", flush=True)
        return rc
    rc = _run_binary(root, "--parity-json")
    if rc:
        print("[FAIL] Rust parity probe failed.", flush=True)
        return rc
    rc = _run_binary(root, "--write-evidence", str(root / ".forge" / "native" / "parity-latest.json"))
    if rc:
        print("[FAIL] Rust evidence receipt failed.", flush=True)
        return rc
    print("[PASS] Rust SHADOW gate GREEN. Python ForgePY remains operational authority.", flush=True)
    return 0


def run(root: Path, action: str) -> int:
    row = status(root)
    if action == "status":
        print(json.dumps(row, indent=2, sort_keys=True))
        return 0
    if action == "gate":
        return gate(root)
    row, rc = _require_toolchain(root)
    if rc:
        return rc
    if action == "probe":
        return _run_binary(root, "--probe")
    if action == "parity":
        return _run_binary(root, "--parity-json")
    if action == "evidence":
        return _run_binary(root, "--write-evidence", str(root / ".forge" / "native" / "parity-latest.json"))
    if action == "shell-model":
        return _run_binary(root, "--shell-model-json")
    if action == "intelligence":
        return _run_binary(root, "--intelligence-json")
    if action == "stdio":
        return _run_binary(root, "--serve-stdio")
    if action == "run":
        return _launch_gui(root)
    argv = _cargo_command(root, action)
    if argv is None:
        print(f"[FAIL] Unknown Rust lane action: {action}")
        return 2
    return _call(argv, cwd=root)


def main() -> int:
    parser = argparse.ArgumentParser(description="ForgePY-owned Rust successor build/certification lane")
    parser.add_argument(
        "action",
        choices=("status", "check", "test", "build", "build-release", "run", "probe", "parity", "evidence", "shell-model", "intelligence", "stdio", "gate"),
    )
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    return run(Path(args.root).expanduser().resolve(), args.action)


if __name__ == "__main__":
    raise SystemExit(main())
