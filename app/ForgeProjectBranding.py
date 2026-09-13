#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
from typing import Any

PROJECT_BRANDING_VERSION = "FORGEPY-PROJECT-BRANDING-1.1-F743"


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _confined(root: Path, value: str) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.expanduser().resolve()
        candidate.relative_to(root)
        return candidate if candidate.is_file() else None
    except Exception:
        return None


def discover_icon(root: Path, project_name: str = "") -> Path | None:
    """Return a bounded, project-owned icon candidate without recursively scanning the repo."""
    root = root.expanduser().resolve()
    name = str(project_name or root.name).strip()
    control = _safe_json(root / "project.control.json")
    project = control.get("project") if isinstance(control.get("project"), dict) else {}
    branding = control.get("branding") if isinstance(control.get("branding"), dict) else {}

    declared = [
        project.get("icon"),
        branding.get("icon"),
        control.get("icon"),
    ]
    for value in declared:
        path = _confined(root, str(value or ""))
        if path is not None:
            return path

    names = [name, name.replace(" ", ""), root.name, root.name.replace(" ", "")]
    dedup_names: list[str] = []
    for value in names:
        value = value.strip()
        if value and value.casefold() not in {x.casefold() for x in dedup_names}:
            dedup_names.append(value)

    candidates: list[Path] = []
    for value in dedup_names:
        candidates.extend(
            [
                root / "assets" / "branding" / f"{value}.png",
                root / "assets" / "branding" / f"{value}.ico",
                root / f"{value}.png",
                root / f"{value}.ico",
                root / f"{value}.exe",
            ]
        )
    candidates.extend(
        [
            root / "assets" / "branding" / "icon.png",
            root / "assets" / "branding" / "icon.ico",
            root / "assets" / "icon.png",
            root / "assets" / "icon.ico",
            root / "resources" / "icon.png",
            root / "resources" / "icon.ico",
            root / "src-tauri" / "icons" / "icon.png",
            root / "src-tauri" / "icons" / "icon.ico",
            root / "icon.png",
            root / "icon.ico",
        ]
    )
    for path in candidates:
        try:
            if path.is_file():
                return path.resolve()
        except Exception:
            continue
    return None


def _scale_photo(photo: Any, size: int) -> Any:
    try:
        width = max(1, int(photo.width()))
        height = max(1, int(photo.height()))
        factor = max(1, (max(width, height) + size - 1) // size)
        return photo.subsample(factor, factor) if factor > 1 else photo
    except Exception:
        return photo


def _windows_icon_photo(gui: Any, path: Path, size: int) -> Any | None:
    if os.name != "nt":
        return None
    try:
        from ctypes import wintypes

        class SHFILEINFOW(ctypes.Structure):
            _fields_ = [
                ("hIcon", wintypes.HICON),
                ("iIcon", ctypes.c_int),
                ("dwAttributes", wintypes.DWORD),
                ("szDisplayName", wintypes.WCHAR * 260),
                ("szTypeName", wintypes.WCHAR * 80),
            ]

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        info = SHFILEINFOW()
        # SHGFI_ICON | SHGFI_SMALLICON. For .ico/.exe this returns the file's shell icon.
        if not shell32.SHGetFileInfoW(str(path), 0, ctypes.byref(info), ctypes.sizeof(info), 0x000000100 | 0x000000001):
            return None
        hdc = gdi32.CreateCompatibleDC(0)
        bits = ctypes.c_void_p()
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = size
        bmi.bmiHeader.biHeight = -size
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        bitmap = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), 0, 0)
        if not bitmap:
            user32.DestroyIcon(info.hIcon)
            gdi32.DeleteDC(hdc)
            return None
        old = gdi32.SelectObject(hdc, bitmap)
        brush = gdi32.CreateSolidBrush(0x001A1511)  # PANEL #11151a as COLORREF
        rect = wintypes.RECT(0, 0, size, size)
        user32.FillRect(hdc, ctypes.byref(rect), brush)
        user32.DrawIconEx(hdc, 0, 0, info.hIcon, size, size, 0, 0, 0x0003)
        raw = ctypes.string_at(bits, size * size * 4)
        image = gui.tk.PhotoImage(width=size, height=size)
        for y in range(size):
            row = []
            for x in range(size):
                offset = (y * size + x) * 4
                b, g, r, _a = raw[offset:offset + 4]
                row.append(f"#{r:02x}{g:02x}{b:02x}")
            image.put("{" + " ".join(row) + "}", to=(0, y))
        gdi32.SelectObject(hdc, old)
        gdi32.DeleteObject(brush)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(hdc)
        user32.DestroyIcon(info.hIcon)
        return image
    except Exception:
        return None


def project_icon_photo(gui: Any, root: Path, project_name: str = "", size: int = 18) -> tuple[Any | None, Path | None]:
    path = discover_icon(root, project_name)
    if path is None:
        return None, None
    suffix = path.suffix.casefold()
    if suffix in {".png", ".gif", ".ppm", ".pgm"}:
        try:
            return _scale_photo(gui.tk.PhotoImage(file=str(path)), size), path
        except Exception:
            pass
    image = _windows_icon_photo(gui, path, size)
    return image, path


__all__ = ["PROJECT_BRANDING_VERSION", "discover_icon", "project_icon_photo"]
