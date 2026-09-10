#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from PCCSurfaceCommon import BackendClient, ProjectContract, ProjectRegistry, SurfaceError
from ForgeGui import ForgeGui, GUI_VERSION
from ForgeConsole import run_console
from ForgeVersion import VERSION as FORGE_VERSION

STANDALONE_VERSION = f"FORGE-STANDALONE-{FORGE_VERSION}"


def _valid_root(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        return None
    return resolved if resolved.is_dir() else None


def _registry_root() -> Path | None:
    registry = ProjectRegistry()
    active = registry.active_registry_id()
    entries = registry.entries()
    if active:
        for entry in entries:
            if entry.registry_id == active:
                root = _valid_root(entry.root)
                if root is not None:
                    return root
    existing = [root for root in (_valid_root(entry.root) for entry in entries) if root is not None]
    if len(existing) == 1:
        return existing[0]
    return None


def _choose_root() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise SurfaceError(f"Tkinter is required to choose a project folder: {exc}") from exc
    chooser = tk.Tk()
    chooser.withdraw()
    try:
        raw = filedialog.askdirectory(title="Select a project folder for Forge", mustexist=True)
    finally:
        chooser.destroy()
    return _valid_root(Path(raw)) if raw else None


def resolve_target(raw: str | None, *, force_choose: bool = False) -> Path | None:
    if raw:
        root = _valid_root(Path(raw))
        if root is None:
            raise SurfaceError(f"Project root does not exist: {raw}")
        return root
    if not force_choose:
        root = _registry_root()
        if root is not None:
            return root
    return _choose_root()


def self_test(root: Path | None = None) -> int:
    print(f"PASS standalone-version={STANDALONE_VERSION}")
    print(f"PASS gui-version={GUI_VERSION}")
    print(f"PASS python={sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        print("FAIL Python 3.11 or newer is required.")
        return 1
    try:
        import tkinter as tk
        print(f"PASS tkinter={tk.TkVersion}")
    except Exception as exc:
        print(f"FAIL tkinter={exc}")
        return 1
    try:
        import PCCProjectDiscovery  # noqa: F401
        import PCCAutoAdapter  # noqa: F401
        import PCCOperationHost  # noqa: F401
        import PCCRepoHygiene  # noqa: F401
        import PCCVaultCatalog  # noqa: F401
        import VaultPaths  # noqa: F401
        import ForgeHealth  # noqa: F401
        import VaultIntake  # noqa: F401
        import VaultPatchEngine  # noqa: F401
        print("PASS forge-modules=loaded")
    except Exception as exc:
        print(f"FAIL universal-modules={exc}")
        return 1
    registry = ProjectRegistry()
    print(f"PASS registry={registry.path}")
    print(f"PASS registered-projects={len(registry.entries())}")
    if root is not None:
        try:
            contract = ProjectContract.load(root)
            print(f"PASS project={contract.name}:{contract.kind}")
            backend = BackendClient(root, contract)
            print(f"PASS provider={backend.provider_label}")
        except Exception as exc:
            print(f"WARN project-provider={exc}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forge — Universal Project Control Center")
    parser.add_argument("--root", help="Project folder to open initially")
    parser.add_argument("--choose", action="store_true", help="Always show the project-folder picker")
    parser.add_argument("--self-test", action="store_true", help="Verify the standalone Forge package")
    parser.add_argument("--console", action="store_true", help="Use the guaranteed console fallback instead of the GUI")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        root = _valid_root(Path(args.root)) if args.root else None
        return self_test(root)
    target = resolve_target(args.root, force_choose=args.choose)
    if target is None:
        return 0
    if args.console:
        return run_console(target)
    return ForgeGui(target).run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SurfaceError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
