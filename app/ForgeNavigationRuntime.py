#!/usr/bin/env python3
from __future__ import annotations

import time
from typing import Any

NAVIGATION_VERSION = "FORGEPY-NAVIGATION-RUNTIME-1.0-F740"
DEFAULT_DEBOUNCE_MS = 28


def install_class(cls: type[Any]) -> type[Any]:
    if getattr(cls, "_forge_navigation_f740_installed", False):
        return cls
    cls._forge_navigation_f740_installed = True

    commit_tab = cls._show_app_tab

    def show_app_tab(self: Any, name: str) -> None:
        """Coalesce rapid tab clicks and preserve the last stable frame on failure."""
        requested = str(name or "")
        if not requested:
            return

        current = str(getattr(self, "_current_app_tab", "") or "")
        pending = str(getattr(self, "_forge_nav_pending_target", "") or "")
        if requested == current and not pending:
            return

        generation = int(getattr(self, "_forge_nav_generation", 0) or 0) + 1
        self._forge_nav_generation = generation
        self._forge_nav_pending_target = requested

        try:
            previous_after = getattr(self, "_forge_nav_after_id", None)
            if previous_after:
                self.window.after_cancel(previous_after)
        except Exception:
            pass

        def commit() -> None:
            if generation != int(getattr(self, "_forge_nav_generation", 0) or 0):
                return
            target = str(getattr(self, "_forge_nav_pending_target", "") or requested)
            self._forge_nav_pending_target = ""
            previous = str(getattr(self, "_current_app_tab", "") or "")
            started = time.perf_counter()
            try:
                commit_tab(self, target)
            except Exception as exc:
                try:
                    if previous:
                        frame = (getattr(self, "_app_frames", {}) or {}).get(previous)
                        if frame is not None and not frame.winfo_manager():
                            frame.pack(fill="both", expand=True)
                        self._current_app_tab = previous
                except Exception:
                    pass
                try:
                    self._append_log(f"[FAIL] Navigation to {target} failed: {exc}\n", "fail")
                except Exception:
                    pass
                return
            finally:
                try:
                    self._forge_nav_after_id = None
                except Exception:
                    pass

            try:
                from ForgePerformance import record
                elapsed = (time.perf_counter() - started) * 1000.0
                record("navigation-commit", elapsed, 120.0, {"target": target, "previous": previous})
            except Exception:
                pass

        try:
            self._forge_nav_after_id = self.window.after(DEFAULT_DEBOUNCE_MS, commit)
        except Exception:
            commit()

    cls._show_app_tab = show_app_tab
    return cls
