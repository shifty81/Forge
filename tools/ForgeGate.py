#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
from ForgeGreen import certify_green


def emit(kind: str, text: str) -> None:
    print(f"[{kind}] {text}", flush=True)


def python_syntax() -> bool:
    files = sorted([*APP.glob("*.py"), *(ROOT / "tests").glob("*.py"), *(ROOT / "tools").glob("*.py")])
    try:
        for path in files:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except Exception as exc:
        emit("FAIL", f"Python syntax: {exc}")
        return False
    emit("PASS", f"Python syntax: {len(files)} file(s)")
    return True


def self_test() -> bool:
    cp = subprocess.run(
        [sys.executable, str(APP / "ForgeStandalone.py"), "--self-test"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    print(cp.stdout, end="")
    if cp.returncode != 0:
        emit("FAIL", f"Forge standalone self-test exited {cp.returncode}")
        return False
    emit("PASS", "Forge standalone self-test")
    return True


def unit_tests() -> bool:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(APP) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    cp = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    print(cp.stdout, end="")
    if cp.returncode != 0:
        emit("FAIL", f"Forge unit tests exited {cp.returncode}")
        return False
    emit("PASS", "Forge unit tests")
    return True


def contract_check() -> bool:
    path = ROOT / "project.control.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        project = data.get("project") or {}
        if str(project.get("id") or "") != "forge-project-control-center":
            raise ValueError("unexpected Forge project id")
        commands = [x for x in data.get("commands", []) if isinstance(x, dict)]
        if not any(x.get("key") == "gate.full" for x in commands):
            raise ValueError("gate.full command missing")
    except Exception as exc:
        emit("FAIL", f"Forge project contract: {exc}")
        return False
    emit("PASS", "Forge project contract")
    return True


def manifest_check() -> bool:
    path = ROOT / "FORGE_PACKAGE_MANIFEST.json"
    if not path.is_file():
        emit("WARN", "Package manifest not generated yet; run tools/BuildForgeManifest.py before release packaging")
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        declared = data.get("files") or []
        import hashlib
        for row in declared:
            file_path = ROOT / str(row["path"])
            if not file_path.is_file():
                raise ValueError(f"missing manifest file: {row['path']}")
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if digest != row["sha256"]:
                raise ValueError(f"hash mismatch: {row['path']}")
    except Exception as exc:
        emit("FAIL", f"Package manifest: {exc}")
        return False
    emit("PASS", f"Package manifest: {len(declared)} file(s)")
    return True


def full() -> int:
    checks = [contract_check, python_syntax, self_test, unit_tests, manifest_check]
    for check in checks:
        if not check():
            emit("FAIL", "FORGE FULL QUALITY GATE FAILED")
            return 1
    try:
        green = certify_green(ROOT, gate="full")
        emit("PASS", f"Forge GREEN authority: {green.get('sourceFileCount', 0)} governed file(s)")
    except Exception as exc:
        emit("FAIL", f"Forge GREEN authority write failed: {exc}")
        return 1
    emit("PASS", "FORGE FULL QUALITY GATE GREEN")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Forge self-hosted quality gate")
    ap.add_argument("action", choices=("full", "quick", "build", "self-test"))
    ns = ap.parse_args(argv)
    if ns.action == "self-test":
        return 0 if self_test() else 1
    if ns.action == "build":
        return 0 if python_syntax() else 1
    if ns.action == "quick":
        return 0 if all(check() for check in (contract_check, python_syntax, self_test)) else 1
    return full()


if __name__ == "__main__":
    raise SystemExit(main())
