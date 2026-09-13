#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

LAYOUT_VERSION = "FORGEPY-LAYOUT-1.0-F630"

# The global quick bar, content/console PanedWindow and status bar already share
# the same 10 px center-host gutter in the base GUI. These values normalize what
# lives *inside* the two global panes.
SURFACE_INSET_X = 8
SURFACE_INSET_Y = 6
CONSOLE_INSET_X = 8
CONSOLE_TOP_Y = 6
CONSOLE_BOTTOM_Y = 6
PROJECT_CENTER_INSET_X = 8
PROJECT_CENTER_INSET_Y = 6


def _pack_configure(widget: Any, **kwargs: Any) -> None:
    try:
        if str(widget.winfo_manager()) == "pack":
            widget.pack_configure(**kwargs)
    except Exception:
        pass


def _direct_shell(frame: Any) -> Any | None:
    try:
        children = list(frame.winfo_children())
    except Exception:
        return None
    # The app frames normally own exactly one surface shell. Prefer the first
    # packed child so lazy/hidden compatibility controls are not moved.
    for child in children:
        try:
            if str(child.winfo_manager()) == "pack":
                return child
        except Exception:
            continue
    return None


def _normalize_console(gui: Any) -> None:
    panel = getattr(gui, "console_panel", None)
    if panel is None:
        return

    # Header / body / command row use the same horizontal inset as normal pages.
    try:
        children = list(panel.winfo_children())
    except Exception:
        children = []

    # The first packed child is the console title bar in the canonical shell.
    packed = []
    for child in children:
        try:
            if str(child.winfo_manager()) == "pack":
                packed.append(child)
        except Exception:
            pass

    if packed:
        _pack_configure(
            packed[0],
            fill="x",
            padx=CONSOLE_INSET_X,
            pady=(CONSOLE_TOP_Y, 5),
        )

    try:
        body = gui.console_text.master
        _pack_configure(body, fill="both", expand=True, padx=CONSOLE_INSET_X, pady=(0, 4))
    except Exception:
        pass

    row = getattr(gui, "console_command_row", None)
    if row is not None:
        _pack_configure(
            row,
            fill="x",
            padx=CONSOLE_INSET_X,
            pady=(0, CONSOLE_BOTTOM_Y),
        )


def _normalize_project_workspace(gui: Any) -> None:
    # Project Workspace is special: its direct child is itself a split pane.
    # The old 6px outer inset made its panel borders start lower/inward than
    # the global Forge Console panel. Remove that duplicate gutter.
    panes = getattr(gui, "workspace_panes", None)
    if panes is not None:
        _pack_configure(panes, fill="both", expand=True, padx=0, pady=0)

    # Inside the Project center panel, normalize the old 13x12 padding to match
    # Forge Console's 8x6 content inset.
    content = getattr(gui, "content", None)
    if content is not None:
        _pack_configure(
            content,
            fill="both",
            expand=True,
            padx=PROJECT_CENTER_INSET_X,
            pady=PROJECT_CENTER_INSET_Y,
        )


def _normalize_app_surfaces(gui: Any) -> None:
    frames = getattr(gui, "_app_frames", {}) or {}
    for key, frame in frames.items():
        # Project is governed by the split-pane rule above.
        if key == "Project Workspace":
            continue
        shell = _direct_shell(frame)
        if shell is None:
            continue
        _pack_configure(
            shell,
            fill="both",
            expand=True,
            padx=SURFACE_INSET_X,
            pady=SURFACE_INSET_Y,
        )

    _normalize_project_workspace(gui)


def normalize(gui: Any) -> None:
    """Normalize all visible ForgePY panes without replacing the live GUI source."""
    # Global pane is the geometry authority. Do not let pages add a second
    # unrelated outer margin on top of it.
    panes = getattr(gui, "global_workspace_panes", None)
    if panes is not None:
        _pack_configure(panes, fill="both", expand=True, padx=10, pady=(0, 4))

    # Quick bar and bottom status remain aligned with the same global 10px gutter.
    host = getattr(gui, "_forge_context_quick_host", None)
    if host is not None:
        try:
            quick = host.master
            _pack_configure(quick, fill="x", padx=10, pady=(5, 5))
            _pack_configure(host, fill="x", padx=8, pady=5)
        except Exception:
            pass

    _normalize_app_surfaces(gui)
    _normalize_console(gui)


def schedule(gui: Any, delay_ms: int = 20) -> None:
    """Debounced layout normalization for lazy page builds and window resizing."""
    try:
        old = getattr(gui, "_forge_layout_after_id", None)
        if old:
            gui.window.after_cancel(old)
    except Exception:
        pass

    def apply() -> None:
        gui._forge_layout_after_id = None
        normalize(gui)

    try:
        gui._forge_layout_after_id = gui.window.after(max(1, int(delay_ms)), apply)
    except Exception:
        normalize(gui)
