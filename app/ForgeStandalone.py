#!/usr/bin/env python3
from __future__ import annotations

import argparse
import faulthandler
import os
import sys
import traceback
from pathlib import Path
from typing import Sequence

from ForgeBootstrapLog import trace as bootstrap_trace
from ForgePYVersion import VERSION as FORGE_VERSION

GUI_VERSION = f"FORGEPY-GUI-{FORGE_VERSION}"

# Lazy compatibility hooks.  These names remain patchable/testable without
# importing Tk/ForgeGui before bootstrap diagnostics are active.
ForgeGui = None

def ensure_forgepy_layout():
    from ForgeVaultBootstrap import ensure_layout
    return ensure_layout()

def forgepy_first_run_needed():
    from ForgeFirstRun import needed
    return needed()

def initialize_forgepy_first_run():
    from ForgeFirstRun import initialize
    return initialize()

STANDALONE_VERSION = f"FORGEPY-STANDALONE-{FORGE_VERSION}"


_NATIVE_CRASH_STREAM = None

def _install_crash_diagnostics() -> None:
    """Persist Python/native fatal traces instead of leaving only Windows' crash box."""
    global _NATIVE_CRASH_STREAM
    try:
        from ForgePYPaths import data_root as forgepy_data_root
        log_dir = forgepy_data_root() / "Logs" / "crashes"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
        path = log_dir / f"forgepy-native-{stamp}.log"
        _NATIVE_CRASH_STREAM = path.open("a", encoding="utf-8", buffering=1)
        _NATIVE_CRASH_STREAM.write(f"ForgePY native diagnostics\nPython: {sys.version}\nExecutable: {sys.executable}\n\n")
        faulthandler.enable(file=_NATIVE_CRASH_STREAM, all_threads=True)
        old_hook = sys.excepthook
        def hook(exc_type, exc, tb):
            try:
                traceback.print_exception(exc_type, exc, tb, file=_NATIVE_CRASH_STREAM)
            except Exception:
                pass
            old_hook(exc_type, exc, tb)
        sys.excepthook = hook
    except Exception:
        _NATIVE_CRASH_STREAM = None


def _valid_root(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        return None
    return resolved if resolved.is_dir() else None


def _registry_root() -> Path | None:
    from PCCSurfaceCommon import ProjectRegistry
    registry = ProjectRegistry()
    active = registry.active_registry_id()
    entries = registry.entries()
    if active:
        for entry in entries:
            if entry.registry_id == active:
                root = _valid_root(entry.root)
                if root is not None:
                    return root

    # A stale/missing activeProject must never make normal ForgePY startup
    # disappear. Fall back to the most recently opened valid registered project.
    existing = [
        entry for entry in entries
        if _valid_root(entry.root) is not None
    ]
    if existing:
        existing.sort(key=lambda entry: str(entry.last_opened_utc or ""), reverse=True)
        return _valid_root(existing[0].root)
    return None


def _forgepy_self_root() -> Path:
    """Safe shell project used when a machine has no usable active project yet."""
    return Path(__file__).resolve().parents[1]


def _choose_root() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        from PCCSurfaceCommon import SurfaceError
        raise SurfaceError(f"Tkinter is required to choose a project folder: {exc}") from exc
    chooser = tk.Tk()
    chooser.withdraw()
    try:
        raw = filedialog.askdirectory(title="Select a project folder for ForgePY", mustexist=True)
    finally:
        chooser.destroy()
    return _valid_root(Path(raw)) if raw else None


def resolve_target(raw: str | None, *, force_choose: bool = False) -> Path | None:
    if raw:
        root = _valid_root(Path(raw))
        if root is None:
            from PCCSurfaceCommon import SurfaceError
            raise SurfaceError(f"Project root does not exist: {raw}")
        return root

    if force_choose:
        # Explicit --choose is the only normal path that may present/cancel a
        # folder picker before the main shell exists.
        return _choose_root()

    root = _registry_root()
    if root is not None:
        return root

    # ForgePY is itself a valid registered project.  Booting its own project
    # contract gives the Projects surface a stable shell even on a clean PC,
    # after a registry migration, or when activeProject was lost.
    return _forgepy_self_root()


def self_test(root: Path | None = None) -> int:
    bootstrap_trace("SELF_TEST_START")
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
        import ForgePYPaths  # noqa: F401
        import ForgePYHealth  # noqa: F401
        import ForgePYIntake  # noqa: F401
        import ForgePYPatchEngine  # noqa: F401
        import ForgePYSourceControl  # noqa: F401
        import ForgePYInternalGit  # noqa: F401
        import ForgePYBrand  # noqa: F401
        import ForgeRuntimeServices  # noqa: F401
        import ForgeToolRuntime  # noqa: F401
        import ForgePluginRuntime  # noqa: F401
        import ForgeAdapterRegistry  # noqa: F401
        import ForgeBackupRuntime  # noqa: F401
        import ForgeReleasePipeline  # noqa: F401
        import ForgeCertification  # noqa: F401
        import ForgeSupportBundle  # noqa: F401
        import ForgeGuiTasks  # noqa: F401
        import ForgeCache  # noqa: F401
        import ForgeUiMetrics  # noqa: F401
        import ForgeProjectSnapshot  # noqa: F401
        import ForgeVersionConstraints  # noqa: F401
        import ForgeToolForms  # noqa: F401
        import ForgeToolOutput  # noqa: F401
        import ForgeToolPromotionManager  # noqa: F401
        import ForgeToolchainProviders  # noqa: F401
        import ForgeVaultFTS  # noqa: F401
        import ForgeVaultOwnership  # noqa: F401
        import ForgeVaultWatch  # noqa: F401
        import ForgeGitConflict  # noqa: F401
        import ForgeGitManager  # noqa: F401
        import ForgeRepoTreeCache  # noqa: F401
        import ForgeBackupCatalog  # noqa: F401
        import ForgeRestoreTransaction  # noqa: F401
        import ForgeRecoveryCatalog  # noqa: F401
        import ForgeScheduler  # noqa: F401
        import ForgeJobRecovery  # noqa: F401
        import ForgeNotifications  # noqa: F401
        import ForgeHeadless  # noqa: F401
        import ForgeExeBuild  # noqa: F401
        import ForgeSigning  # noqa: F401
        import ForgeInstallerManifest  # noqa: F401
        import ForgeSelfUpdateRuntime  # noqa: F401
        import ForgePluginHost  # noqa: F401
        import ForgeSecurityV2  # noqa: F401
        import ForgeMigrations  # noqa: F401
        import ForgePerfTrace  # noqa: F401
        import ForgeCommandAvailability  # noqa: F401
        import ForgeAdapterCompliance  # noqa: F401
        import ForgeHealthV3  # noqa: F401
        import ForgeHelpIndex  # noqa: F401
        print("PASS forgepy-modules=loaded")
    except Exception as exc:
        print(f"FAIL universal-modules={exc}")
        return 1
    from PCCSurfaceCommon import BackendClient, ProjectContract, ProjectRegistry
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


def _report_fatal_startup_error(exc: BaseException) -> None:
    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        if _NATIVE_CRASH_STREAM is not None:
            _NATIVE_CRASH_STREAM.write("\nFATAL STARTUP ERROR\n" + detail + "\n")
            _NATIVE_CRASH_STREAM.flush()
    except Exception:
        pass
    try:
        print(detail, file=sys.stderr)
    except Exception:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "ForgePY could not start",
            "ForgePY hit a startup error before the main window could stay open.\n\n"
            f"{exc}\n\n"
            "Run ForgePY.cmd for the foreground diagnostic console. "
            "A crash/startup log was also written under the ForgePY Logs/crashes folder.",
            parent=root,
        )
        root.destroy()
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ForgePY — Universal Project Control Center")
    parser.add_argument("--root", help="Project folder to open initially")
    parser.add_argument("--choose", action="store_true", help="Always show the project-folder picker")
    parser.add_argument("--self-test", action="store_true", help="Verify the standalone Forge package")
    parser.add_argument("--console", action="store_true", help="Use the guaranteed console fallback instead of the GUI")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    bootstrap_trace("STANDALONE_MAIN_ENTER")
    _install_crash_diagnostics()
    bootstrap_trace("CRASH_DIAGNOSTICS_INSTALLED", native_log=bool(_NATIVE_CRASH_STREAM))
    args = build_parser().parse_args(argv)
    bootstrap_trace("ARGS_PARSED", self_test=args.self_test, console=args.console, choose=args.choose, root=args.root)
    if args.self_test:
        root = _valid_root(Path(args.root)) if args.root else None
        return self_test(root)

    bootstrap_trace("TARGET_RESOLVE_START")
    target = resolve_target(args.root, force_choose=args.choose)
    bootstrap_trace("TARGET_RESOLVE_PASS", target=str(target) if target else "")
    if target is None:
        return 0

    if args.console:
        bootstrap_trace("IMPORT_CONSOLE_START")
        from ForgeConsole import run_console
        bootstrap_trace("IMPORT_CONSOLE_PASS")
        return run_console(target)

    bootstrap_trace("IMPORT_LAYOUT_START")
    bootstrap_trace("IMPORT_LAYOUT_PASS")
    ensure_forgepy_layout()
    bootstrap_trace("LAYOUT_ENSURED")
    if forgepy_first_run_needed():
        bootstrap_trace("FIRST_RUN_INIT_START")
        initialize_forgepy_first_run()
        bootstrap_trace("FIRST_RUN_INIT_PASS")

    # Critically, ForgeGui is imported only after diagnostics + package-local
    # bootstrap logging are active. If a hard import/native failure occurs, the
    # last durable bootstrap phase identifies the exact boundary.
    global ForgeGui
    bootstrap_trace("IMPORT_FORGE_GUI_START")
    if ForgeGui is None:
        from ForgeGui import ForgeGui as _ForgeGui
        ForgeGui = _ForgeGui
    bootstrap_trace("IMPORT_FORGE_GUI_PASS")
    bootstrap_trace("FORGE_GUI_CONSTRUCT_START", target=str(target))
    return ForgeGui(target).run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _report_fatal_startup_error(exc)
        raise SystemExit(1)
