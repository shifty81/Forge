#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import os
import queue
import sys
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Sequence

from ForgePYBrand import ICON_ICO


@dataclass(frozen=True)
class TrayCommand:
    key: str
    label: str
    separator: bool = False
    enabled: bool = True


DEFAULT_MENU: tuple[TrayCommand, ...] = (
    TrayCommand("open", "Open ForgePY"),
    TrayCommand("projects", "Projects"),
    TrayCommand("workspace", "Project Workspace"),
    TrayCommand("health", "Health"),
    TrayCommand("sep-1", "", separator=True),
    TrayCommand("full-gate", "Full Gate / Certify GREEN"),
    TrayCommand("apply-updates", "Apply Updates"),
    TrayCommand("scan-intake", "Scan Intake"),
    TrayCommand("sep-2", "", separator=True),
    TrayCommand("source-control", "Source Control"),
    TrayCommand("forgejo", "Source Control"),
    TrayCommand("ide", "ForgePY IDE"),
    TrayCommand("cortex", "Cortex"),
    TrayCommand("sep-3", "", separator=True),
    TrayCommand("settings", "Settings"),
    TrayCommand("open-home", "Open ForgePY Home"),
    TrayCommand("open-artifacts", "Open Artifact Central"),
    TrayCommand("sep-4", "", separator=True),
    TrayCommand("exit", "Exit ForgePY"),
)


def supported() -> bool:
    if os.name != "nt":
        return False
    if os.environ.get("FORGEPY_DISABLE_TRAY", "").strip().casefold() in {"1", "true", "yes", "on"}:
        return False
    # F60R65 still used a hand-written ctypes Shell_NotifyIcon callback window.
    # On Python 3.14/64-bit Windows the host reported a native __debugbreak crash
    # after the main GUI opened.  Keep this legacy implementation fail-closed
    # until the packaged ForgePY.exe lane replaces it with a certified tray host.
    if sys.version_info >= (3, 14):
        return os.environ.get("FORGEPY_ENABLE_LEGACY_NATIVE_TRAY", "").strip().casefold() in {"1", "true", "yes", "on"}
    return True


class ForgeTray:
    """Small Windows tray authority implemented directly with Shell_NotifyIcon.

    No third-party tray dependency is required.  Callbacks are never executed on
    the tray thread; they are posted through ``dispatch`` so the Tk thread can
    handle them safely.
    """

    def __init__(
        self,
        dispatch: Callable[[str], None],
        *,
        tooltip: str = "ForgePY",
        menu: Sequence[TrayCommand] = DEFAULT_MENU,
    ) -> None:
        self.dispatch = dispatch
        self.tooltip = tooltip[:127]
        self.menu = tuple(menu)
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._hwnd = 0
        self._nid = None
        self._status_text = "ForgePY"

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._hwnd)

    def start(self) -> bool:
        if not supported() or self.running:
            return self.running
        self._thread = threading.Thread(target=self._run, daemon=True, name="ForgeTray")
        self._thread.start()
        self._ready.wait(2.5)
        return self.running

    def stop(self) -> None:
        self._stop.set()
        if supported() and self._hwnd:
            try:
                ctypes.windll.user32.PostMessageW(self._hwnd, 0x0010, 0, 0)  # WM_CLOSE
            except Exception:
                pass
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)

    def set_status(self, text: str) -> None:
        self._status_text = str(text or "ForgePY")[:127]
        if not supported() or not self._hwnd or self._nid is None:
            return
        try:
            self._nid.szTip = self._status_text
            ctypes.windll.shell32.Shell_NotifyIconW(0x00000001, ctypes.byref(self._nid))  # NIM_MODIFY
        except Exception:
            pass

    def notify(self, title: str, message: str) -> None:
        if not supported() or not self._hwnd or self._nid is None:
            return
        try:
            self._nid.uFlags |= 0x00000010  # NIF_INFO
            self._nid.szInfoTitle = str(title)[:63]
            self._nid.szInfo = str(message)[:255]
            self._nid.dwInfoFlags = 0x00000001  # NIIF_INFO
            ctypes.windll.shell32.Shell_NotifyIconW(0x00000001, ctypes.byref(self._nid))
            self._nid.uFlags &= ~0x00000010
        except Exception:
            pass

    def _run(self) -> None:  # pragma: no cover - exercised on Windows hosts
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        kernel32 = ctypes.windll.kernel32

        # ctypes assumes c_int for untyped Win32 APIs.  That truncates pointer-sized
        # HWND/LPARAM/LRESULT values on 64-bit Windows and caused the tray callback
        # OverflowError seen in Python 3.14.  Declare every pointer-sensitive API
        # used by the hidden message window before the first call.
        LRESULT = ctypes.c_ssize_t
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.RegisterClassW.argtypes = [ctypes.c_void_p]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        user32.LoadIconW.restype = wintypes.HICON
        user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.CreatePopupMenu.argtypes = []
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.TrackPopupMenu.argtypes = [
            wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, ctypes.c_void_p,
        ]
        user32.TrackPopupMenu.restype = wintypes.UINT
        user32.DestroyMenu.argtypes = [wintypes.HMENU]
        user32.DestroyMenu.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        user32.GetCursorPos.argtypes = [ctypes.c_void_p]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.DestroyWindow.restype = wintypes.BOOL
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.PostQuitMessage.restype = None
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.c_void_p]
        shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
        user32.RegisterWindowMessageW.restype = wintypes.UINT
        user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
        user32.AppendMenuW.restype = wintypes.BOOL
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.PostMessageW.restype = wintypes.BOOL

        WM_USER = 0x0400
        WM_TRAY = WM_USER + 41
        WM_COMMAND = 0x0111
        WM_DESTROY = 0x0002
        WM_CLOSE = 0x0010
        WM_LBUTTONDBLCLK = 0x0203
        WM_RBUTTONUP = 0x0205
        WM_CONTEXTMENU = 0x007B
        NIM_ADD = 0x00000000
        NIM_DELETE = 0x00000002
        NIM_SETVERSION = 0x00000004
        NOTIFYICON_VERSION_4 = 4
        NIF_MESSAGE = 0x00000001
        NIF_ICON = 0x00000002
        NIF_TIP = 0x00000004
        MF_STRING = 0x00000000
        MF_SEPARATOR = 0x00000800
        MF_GRAYED = 0x00000001
        TPM_RIGHTBUTTON = 0x0002
        TPM_RETURNCMD = 0x0100
        IDI_APPLICATION = 32512
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")

        class WNDCLASS(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256),
                ("uTimeoutOrVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", wintypes.HICON),
            ]

        CMD_BASE = 41000
        command_by_id: dict[int, str] = {}

        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        def show_menu(hwnd: int) -> None:
            menu_handle = user32.CreatePopupMenu()
            if not menu_handle:
                return
            try:
                command_by_id.clear()
                next_id = CMD_BASE
                # Status is informational and deliberately disabled.
                user32.AppendMenuW(menu_handle, MF_STRING | MF_GRAYED, 0, self._status_text)
                user32.AppendMenuW(menu_handle, MF_SEPARATOR, 0, None)
                for item in self.menu:
                    if item.separator:
                        user32.AppendMenuW(menu_handle, MF_SEPARATOR, 0, None)
                        continue
                    flags = MF_STRING | (0 if item.enabled else MF_GRAYED)
                    user32.AppendMenuW(menu_handle, flags, next_id, item.label)
                    command_by_id[next_id] = item.key
                    next_id += 1
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                user32.SetForegroundWindow(hwnd)
                selected = user32.TrackPopupMenu(menu_handle, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, hwnd, None)
                if selected and int(selected) in command_by_id:
                    self.dispatch(command_by_id[int(selected)])
            finally:
                user32.DestroyMenu(menu_handle)

        @WNDPROC
        def wndproc(hwnd, msg, wparam, lparam):
            # Explorer restarts destroy notification-area icons. Re-register the
            # Vault icon when Windows broadcasts TaskbarCreated so background
            # services do not become unreachable after an Explorer restart.
            if taskbar_created and msg == taskbar_created and self._nid is not None:
                try:
                    shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid))
                    self._nid.uTimeoutOrVersion = NOTIFYICON_VERSION_4
                    shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(self._nid))
                except Exception:
                    pass
                return 0
            if msg == WM_TRAY:
                event = int(lparam) & 0xFFFF
                if event == WM_LBUTTONDBLCLK:
                    self.dispatch("open")
                    return 0
                if event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    show_menu(hwnd)
                    return 0
            if msg == WM_COMMAND:
                key = command_by_id.get(int(wparam) & 0xFFFF)
                if key:
                    self.dispatch(key)
                    return 0
            if msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        class_name = f"ForgePYTrayWindow_{os.getpid()}"
        hinstance = kernel32.GetModuleHandleW(None)
        app_icon = 0
        try:
            if Path(ICON_ICO).is_file():
                app_icon = int(user32.LoadImageW(None, str(ICON_ICO), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE) or 0)
        except Exception:
            app_icon = 0
        if not app_icon:
            app_icon = int(user32.LoadIconW(None, ctypes.cast(ctypes.c_void_p(IDI_APPLICATION), wintypes.LPCWSTR)) or 0)
        wc = WNDCLASS()
        wc.lpfnWndProc = ctypes.cast(wndproc, ctypes.c_void_p).value
        wc.hInstance = hinstance
        wc.lpszClassName = class_name
        wc.hIcon = app_icon
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            self._ready.set()
            return
        hwnd = user32.CreateWindowExW(0, class_name, "ForgePY Tray", 0, 0, 0, 0, 0, 0, 0, hinstance, None)
        if not hwnd:
            self._ready.set()
            return
        self._hwnd = int(hwnd)
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = app_icon
        nid.szTip = self.tooltip
        self._nid = nid
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        # Use the current notification-icon behavior while retaining the legacy
        # right-click fallback. The context menu remains owned by Forge.
        nid.uTimeoutOrVersion = NOTIFYICON_VERSION_4
        shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(nid))
        self._ready.set()
        try:
            msg = wintypes.MSG()
            user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            user32.GetMessageW.restype = wintypes.BOOL
            user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
            user32.TranslateMessage.restype = wintypes.BOOL
            user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
            user32.DispatchMessageW.restype = LRESULT
            while not self._stop.is_set() and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            try:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            except Exception:
                pass
            self._hwnd = 0
            self._nid = None


VaultTray = ForgeTray  # compatibility alias for pre-F60R3 callers

__all__ = ["TrayCommand", "DEFAULT_MENU", "ForgeTray", "VaultTray", "supported"]
