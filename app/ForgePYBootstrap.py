#!/usr/bin/env python3
from __future__ import annotations
import os, sys, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ForgeBootstrapLog import initialize, trace, path as bootstrap_log_path

initialize()
trace("PROCESS_START", python=sys.version, executable=sys.executable, argv=sys.argv, cwd=os.getcwd(), app=str(HERE))


def _visible_error(exc: BaseException) -> None:
    trace("BOOTSTRAP_FATAL", error=repr(exc), traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    try:
        import tkinter as tk
        from tkinter import messagebox
        r=tk.Tk(); r.withdraw()
        messagebox.showerror(
            "ForgePY startup failure",
            f"ForgePY failed before the main window became stable.\n\n{exc}\n\n"
            f"Bootstrap log:\n{bootstrap_log_path()}", parent=r)
        r.destroy()
    except Exception as dialog_exc:
        trace("BOOTSTRAP_ERROR_DIALOG_FAILED", error=repr(dialog_exc))


def main() -> int:
    trace("IMPORT_FORGE_STANDALONE_START")
    try:
        import ForgeStandalone
    except BaseException as exc:
        _visible_error(exc)
        return 101
    trace("IMPORT_FORGE_STANDALONE_PASS")
    try:
        trace("FORGE_STANDALONE_MAIN_START")
        rc=int(ForgeStandalone.main(sys.argv[1:]) or 0)
        trace("FORGE_STANDALONE_MAIN_RETURN", returncode=rc)
        return rc
    except BaseException as exc:
        _visible_error(exc)
        return 102


if __name__ == "__main__":
    rc=main()
    trace("PROCESS_EXIT", returncode=rc)
    raise SystemExit(rc)
