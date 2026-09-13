#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import importlib.abc
import importlib.machinery
import inspect
import os
import re
import sys
from pathlib import Path
from typing import Any

COMPAT_VERSION = "FORGEPY-RUNTIME-COMPAT-F700"
_TARGET = "ForgeSimplifiedUX"


def _fixed_windows_drop(module: Any, gui: Any) -> None:
    if os.name != "nt" or getattr(gui, "_forge_drop_installed", False):
        return
    try:
        gui.window.update_idletasks()
        hwnd_value = int(gui.window.winfo_id())
        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        WM_DROPFILES = 0x0233
        GWL_WNDPROC = -4
        HWND = ctypes.c_void_p
        UINT = ctypes.c_uint
        WPARAM = ctypes.c_size_t
        LPARAM = ctypes.c_ssize_t
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

        get_long = user32.GetWindowLongPtrW
        get_long.argtypes = [HWND, ctypes.c_int]
        get_long.restype = ctypes.c_void_p

        set_long = user32.SetWindowLongPtrW
        set_long.argtypes = [HWND, ctypes.c_int, ctypes.c_void_p]
        set_long.restype = ctypes.c_void_p

        call_proc = user32.CallWindowProcW
        call_proc.argtypes = [ctypes.c_void_p, HWND, UINT, WPARAM, LPARAM]
        call_proc.restype = LRESULT

        shell32.DragAcceptFiles.argtypes = [HWND, ctypes.c_bool]
        shell32.DragAcceptFiles.restype = None
        shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, UINT, ctypes.c_wchar_p, UINT]
        shell32.DragQueryFileW.restype = UINT
        shell32.DragFinish.argtypes = [ctypes.c_void_p]
        shell32.DragFinish.restype = None

        hwnd = HWND(hwnd_value)
        old_proc = get_long(hwnd, GWL_WNDPROC)
        if not old_proc:
            raise OSError("GetWindowLongPtrW returned a null WNDPROC")

        def wndproc(hWnd: Any, msg: int, wParam: int, lParam: int) -> int:
            if msg == WM_DROPFILES:
                hdrop = ctypes.c_void_p(int(wParam))
                try:
                    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
                    paths: list[Path] = []
                    for index in range(int(count)):
                        length = shell32.DragQueryFileW(hdrop, index, None, 0)
                        buf = ctypes.create_unicode_buffer(int(length) + 1)
                        shell32.DragQueryFileW(hdrop, index, buf, int(length) + 1)
                        paths.append(Path(buf.value))
                    suffixes = set(getattr(module, "_PATCH_SUFFIXES", {".patch", ".zip"}))
                    ingest = getattr(module, "_ingest_patch")
                    for path in paths:
                        if path.suffix.casefold() in suffixes:
                            gui.window.after(0, lambda p=path: ingest(gui, p))
                finally:
                    shell32.DragFinish(hdrop)
                return 0
            return int(call_proc(old_proc, hWnd, msg, wParam, lParam))

        callback = WNDPROC(wndproc)
        previous = set_long(hwnd, GWL_WNDPROC, ctypes.cast(callback, ctypes.c_void_p))
        if not previous:
            raise OSError("SetWindowLongPtrW failed to install ForgePY drop WNDPROC")

        shell32.DragAcceptFiles(hwnd, True)
        gui._forge_drop_callback = callback
        gui._forge_drop_old_proc = old_proc
        gui._forge_drop_installed = True
        getattr(module, "_safe_log")(gui, "[PASS] Native Windows patch drag/drop enabled (64-bit safe).", "pass")
    except Exception as exc:
        try:
            getattr(module, "_safe_log")(gui, f"[WARN] Native Windows patch drag/drop is unavailable: {exc}", "warn")
        except Exception:
            pass


def patch_simplified_ux(module: Any) -> None:
    try:
        from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
        for name in tuple(vars(module)):
            if name.endswith('_UX_VERSION'):
                setattr(module, name, DISPLAY_BUILD)

        # ForgeGui imported the last certified ForgePYVersion before SimplifiedUX.
        # Replace only its runtime display globals; historical certified-base files
        # remain untouched until executable/release certification.
        gui_module = sys.modules.get("ForgeGui")
        if gui_module is not None:
            setattr(gui_module, "FORGE_VERSION", DISPLAY_VERSION)
            setattr(gui_module, "GUI_VERSION", f"FORGEPY-GUI-{DISPLAY_VERSION}")
        standalone_module = sys.modules.get("ForgeStandalone")
        if standalone_module is not None:
            setattr(standalone_module, "FORGE_VERSION", DISPLAY_VERSION)
            setattr(standalone_module, "GUI_VERSION", f"FORGEPY-GUI-{DISPLAY_VERSION}")

        # Ensure project labels use the bounded current project identity resolver.
        original_identity = getattr(module, "_project_identity", None)
        if callable(original_identity):
            def current_project_identity(root: Path):
                try:
                    from ForgeProjectIdentity import resolve
                    resolved = resolve(Path(root))
                    base = dict(original_identity(Path(root)) or {})
                    if resolved.get("projectVersion"):
                        base["projectVersion"] = resolved["projectVersion"]
                    if resolved.get("projectBuild"):
                        base["projectBuild"] = resolved["projectBuild"]
                    if resolved.get("name"):
                        base["projectName"] = resolved["name"]
                    return base
                except Exception:
                    return original_identity(Path(root))
            module._project_identity = current_project_identity
    except Exception:
        pass
    if not hasattr(module, "re"):
        module.re = re
    try:
        from ForgeStatusCache import patch_runtime_modules, patch_simplified_ux as patch_fast_status
        patch_runtime_modules()
        patch_fast_status(module)
    except Exception:
        pass
    current = getattr(module, "_install_windows_drop", None)
    if current is None:
        return
    try:
        source = inspect.getsource(current)
    except Exception:
        source = ""
    if "call_proc.argtypes" not in source:
        module._install_windows_drop = lambda gui: _fixed_windows_drop(module, gui)

    try:
        from ForgeUnifiedWorkflow import patch_simplified_ux_module
        patch_simplified_ux_module(module)
    except ImportError:
        try:
            from ForgeUnifiedWorkflow import patch_simplified_ux
            patch_simplified_ux(module)
        except Exception:
            pass
    except Exception:
        pass


class _CompatLoader(importlib.abc.Loader):
    def __init__(self, wrapped: Any, finder: "_CompatFinder") -> None:
        self.wrapped = wrapped
        self.finder = finder

    def create_module(self, spec: Any) -> Any:
        create = getattr(self.wrapped, "create_module", None)
        return create(spec) if callable(create) else None

    def exec_module(self, module: Any) -> None:
        self.wrapped.exec_module(module)
        patch_simplified_ux(module)
        try:
            sys.meta_path.remove(self.finder)
        except ValueError:
            pass


class _CompatFinder(importlib.abc.MetaPathFinder):
    _forgepy_f455_compat = True

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname != _TARGET:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        spec.loader = _CompatLoader(spec.loader, self)
        return spec


def install_import_compatibility() -> None:
    try:
        from ForgeBackendCapabilityPatch import install as install_backend_capabilities
        install_backend_capabilities()
    except Exception:
        pass
    loaded = sys.modules.get(_TARGET)
    if loaded is not None:
        patch_simplified_ux(loaded)
        return
    if any(getattr(item, "_forgepy_f455_compat", False) for item in sys.meta_path):
        return
    sys.meta_path.insert(0, _CompatFinder())
