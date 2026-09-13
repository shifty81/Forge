#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
from typing import Sequence
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path: sys.path.insert(0, str(APP))
from ForgeGreen import certify_green
from ForgeContracts import validate_project_contract
from ForgePackagePolicy import is_governed


def emit(kind: str, text: str) -> None:
    print(f"[{kind}] {text}", flush=True)


def python_syntax() -> bool:
    files = sorted([*APP.glob("*.py"), *(ROOT / "tests").glob("*.py"), *(ROOT / "tools").glob("*.py")])
    try:
        for path in files: ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except Exception as exc:
        emit("FAIL", f"Python syntax: {exc}"); return False
    emit("PASS", f"Python syntax: {len(files)} file(s)"); return True


def self_test() -> bool:
    try:
        cp = subprocess.run([sys.executable, str(APP / "ForgePYStandalone.py"), "--self-test"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=180)
    except subprocess.TimeoutExpired:
        emit("FAIL", "ForgePY standalone self-test timed out after 180s"); return False
    print(cp.stdout, end="")
    if cp.returncode != 0: emit("FAIL", f"ForgePY standalone self-test exited {cp.returncode}"); return False
    emit("PASS", "ForgePY standalone self-test"); return True


def unit_tests() -> bool:
    env = os.environ.copy(); env["PYTHONPATH"] = str(APP) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        cp = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=1800)
    except subprocess.TimeoutExpired:
        emit("FAIL", "ForgePY unit tests timed out after 1800s"); return False
    print(cp.stdout, end="")
    if cp.returncode != 0: emit("FAIL", f"ForgePY unit tests exited {cp.returncode}"); return False
    emit("PASS", "ForgePY unit tests"); return True


def rust_shadow_check() -> bool:
    """Certify the governed Rust successor when a Rust toolchain is available.

    The native lane is still SHADOW authority. Missing Cargo is therefore a
    visible skip, not a Python production-gate failure. Once Cargo is present,
    however, a broken governed Rust tree is a real gate failure.
    """
    lane = ROOT / "tools" / "rust" / "ForgeRustLane.py"
    manifest = ROOT / "native" / "forge-rs" / "Cargo.toml"
    if not lane.is_file() or not manifest.is_file():
        emit("FAIL", "Rust SHADOW lane is missing governed source/runner")
        return False
    if not shutil.which("cargo") or not shutil.which("rustc"):
        emit("WARN", "Rust SHADOW gate skipped: cargo/rustc not available on PATH; Python ForgePY remains authority")
        return True
    try:
        cp = subprocess.run(
            [sys.executable, str(lane), "gate", "--root", str(ROOT)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=1800,
        )
    except subprocess.TimeoutExpired:
        emit("FAIL", "Rust SHADOW gate timed out after 1800s")
        return False
    if cp.stdout:
        print(cp.stdout, end="")
    if cp.returncode != 0:
        emit("FAIL", f"Rust SHADOW gate exited {cp.returncode}")
        return False
    emit("PASS", "Rust SHADOW lane")
    return True


def contract_check() -> bool:
    path = ROOT / "project.control.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig")); validate_project_contract(data)
        project = data.get("project") or {}
        if str(project.get("id") or "") != "forgepy": raise ValueError("unexpected ForgePY project id")
        commands = [x for x in data.get("commands", []) if isinstance(x, dict)]
        if not any(x.get("key") == "gate.full" for x in commands): raise ValueError("gate.full command missing")
    except Exception as exc:
        emit("FAIL", f"ForgePY project contract: {exc}"); return False
    emit("PASS", "ForgePY project contract"); return True


def source_authority_check() -> bool:
    try:
        from ForgeSourceTreePolicy import report
        data = report(ROOT)
    except Exception as exc:
        emit("FAIL", f"Source authority check failed: {exc}"); return False
    if not (ROOT / "app").is_dir():
        emit("FAIL", "Canonical root app/ source authority is missing"); return False
    if data.get("legacyMirrorPresent"):
        emit("WARN", f"Legacy ForgePY/app mirror present: {data.get('overlapCount', 0)} overlap(s), {data.get('divergentCount', 0)} divergent. It is excluded from governed release content.")
    else:
        emit("PASS", "Source authority: root app/ only")
    return True



def normalization_check() -> bool:
    try:
        from ForgeNormalizationAudit import audit
        result = audit(ROOT)
    except Exception as exc:
        emit("FAIL", f"Normalization audit failed: {exc}")
        return False
    for row in result.get("failed") or []:
        emit("FAIL", f"Normalization: {row.get('name')}: {row.get('detail')}")
    if not result.get("ok"):
        return False
    emit("PASS", f"Workflow/source/operation normalization: {len(result.get('checks') or [])} invariant(s)")
    return True

def manifest_check() -> bool:
    path = ROOT / "FORGEPY_PACKAGE_MANIFEST.json"
    if not path.is_file(): emit("WARN", "Package manifest not generated yet; run tools/BuildForgePYManifest.py before release packaging"); return True
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig")); declared = data.get("files") or []
        for row in declared:
            rel = str(row["path"])
            if not is_governed(rel): raise ValueError(f"manifest contains non-governed path: {rel}")
            file_path = ROOT / rel
            if not file_path.is_file(): raise ValueError(f"missing manifest file: {rel}")
            h = hashlib.sha256()
            with file_path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
            if h.hexdigest() != row["sha256"]: raise ValueError(f"hash mismatch: {rel}")
    except Exception as exc:
        emit("FAIL", f"Package manifest: {exc}"); return False
    emit("PASS", f"Package manifest: {len(declared)} canonical file(s)"); return True


def full() -> int:
    for check in (contract_check, source_authority_check, normalization_check, python_syntax, self_test, unit_tests, rust_shadow_check, manifest_check):
        if not check(): emit("FAIL", "FORGEPY FULL QUALITY GATE FAILED"); return 1
    try:
        green = certify_green(ROOT, gate="full"); emit("PASS", f"ForgePY GREEN authority: {green.get('sourceFileCount', 0)} governed file(s)")
    except Exception as exc:
        emit("FAIL", f"ForgePY GREEN authority write failed: {exc}"); return 1
    emit("PASS", "FORGEPY FULL QUALITY GATE GREEN"); return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ForgePY self-hosted quality gate")
    ap.add_argument("action", choices=("full", "quick", "build", "self-test")); ns = ap.parse_args(argv)
    if ns.action == "self-test": return 0 if self_test() else 1
    if ns.action == "build": return 0 if python_syntax() else 1
    if ns.action == "quick": return 0 if all(check() for check in (contract_check, source_authority_check, normalization_check, python_syntax, self_test)) else 1
    return full()
if __name__ == "__main__": raise SystemExit(main())
