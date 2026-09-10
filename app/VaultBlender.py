#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from VaultSettings import load_settings


def blender_binary() -> str:
    preferred = str((load_settings().get("tooling") or {}).get("preferredBlenderBinary") or "").strip()
    if preferred and Path(preferred).is_file():
        return preferred
    found = shutil.which("blender") or shutil.which("blender.exe")
    if found:
        return found
    if os.name == "nt":
        base = Path(os.environ.get("PROGRAMFILES") or "C:/Program Files") / "Blender Foundation"
        matches = sorted(base.glob("Blender */blender.exe"), reverse=True) if base.is_dir() else []
        if matches:
            return str(matches[0])
    return ""


def version() -> subprocess.CompletedProcess[str]:
    exe = blender_binary()
    if not exe:
        return subprocess.CompletedProcess([], 127, stdout="Blender executable not found\n")
    return subprocess.run([exe, "--version"], text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def safe_background_args(blend: Path | None = None) -> list[str]:
    args = [blender_binary(), "--background", "--disable-autoexec"]
    if blend is not None:
        args.append(str(blend.expanduser().resolve()))
    return args


def run_script(script: Path, *, blend: Path | None = None, extra: Sequence[str] = ()) -> subprocess.CompletedProcess[str]:
    exe = blender_binary()
    if not exe:
        return subprocess.CompletedProcess([], 127, stdout="Blender executable not found\n")
    script = script.expanduser().resolve()
    argv = safe_background_args(blend) + ["--python-exit-code", "11", "--python", str(script)]
    if extra:
        argv += ["--", *[str(x) for x in extra]]
    return subprocess.run(argv, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def render_frame(blend: Path, frame: int) -> subprocess.CompletedProcess[str]:
    exe = blender_binary()
    if not exe:
        return subprocess.CompletedProcess([], 127, stdout="Blender executable not found\n")
    argv = safe_background_args(blend) + ["--render-frame", str(int(frame))]
    return subprocess.run(argv, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Vault Blender CLI bridge")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("version")
    run = sp.add_parser("run-script"); run.add_argument("script"); run.add_argument("--blend"); run.add_argument("extra", nargs="*")
    rf = sp.add_parser("render-frame"); rf.add_argument("blend"); rf.add_argument("frame", type=int)
    ns = p.parse_args(argv)
    if ns.cmd == "version": cp = version()
    elif ns.cmd == "run-script": cp = run_script(Path(ns.script), blend=Path(ns.blend) if ns.blend else None, extra=ns.extra)
    else: cp = render_frame(Path(ns.blend), ns.frame)
    print(cp.stdout or "", end="")
    return int(cp.returncode)

if __name__ == "__main__":
    raise SystemExit(main())
