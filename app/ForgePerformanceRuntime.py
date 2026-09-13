#!/usr/bin/env python3
from __future__ import annotations

import functools
import sys
import threading
import time
from typing import Any, Callable

from ForgeLoadCoordinator import COORDINATOR

PERFORMANCE_RUNTIME_VERSION = "FORGEPY-PERFORMANCE-RUNTIME-2.0-F700"


def _coordinated(label: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    """Serialize known recursive scanners when they are already running off the Tk thread.

    We intentionally do not change a function's sync/async API. If legacy code calls one of
    these functions on the main thread, preserve behavior and let the performance audit flag it.
    GUI-owned scan entry points already use workers; this wrapper prevents those workers from
    thrashing the disk concurrently.
    """
    if getattr(fn, "_forge_coordinated_scan", False):
        return fn

    @functools.wraps(fn)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if threading.current_thread() is threading.main_thread():
            return fn(*args, **kwargs)
        return COORDINATOR.run_scan(label, lambda: fn(*args, **kwargs), wait_for_idle=2.0)

    wrapped._forge_coordinated_scan = True  # type: ignore[attr-defined]
    return wrapped


def patch_module_aliases() -> None:
    """Patch aliases already imported into ForgeGui after that module is fully loaded."""
    gui = sys.modules.get("ForgeGui")
    if gui is None:
        return

    for name, label in (
        ("vault_drive_scan", "vault-drive-index"),
        ("vault_scan_project", "project-catalog"),
        ("audit_project_tooling", "project-tool-audit"),
        ("audit_registered_tooling", "registered-tool-audit"),
        ("artifact_index_rebuild", "artifact-index"),
        ("forge_drive_census", "drive-census"),
    ):
        fn = getattr(gui, name, None)
        if callable(fn):
            setattr(gui, name, _coordinated(label, fn))

    # ForgeGui baseline performs repository transport hygiene before Tk even creates
    # its first window. Defer that filesystem work until after first paint; operation
    # boundaries still use the authoritative PCCRepoHygiene implementation directly.
    original_hygiene = getattr(gui, "repo_hygiene_prepare", None)
    if callable(original_hygiene) and not getattr(gui, "_forge_startup_hygiene_deferred", False):
        gui._forge_startup_hygiene_deferred = True
        gui._forge_original_repo_hygiene_prepare = original_hygiene

        def deferred_startup_hygiene(root: Any, *, apply: bool = True) -> dict[str, Any]:
            del root, apply
            return {"moved": 0, "deferred": True, "error": ""}

        gui.repo_hygiene_prepare = deferred_startup_hygiene

    # ProjectRegistry.touch() used during GUI construction used to rediscover the
    # already-active project and probe GitHub before first paint. For an existing
    # registry row, update only activeProject/lastOpenedUtc and preserve metadata.
    try:
        from datetime import datetime, timezone
        from pathlib import Path
        from PCCSurfaceCommon import ProjectRegistry, RegisteredProject
        if not getattr(ProjectRegistry, "_forge_fast_existing_touch_f564", False):
            original_touch = ProjectRegistry.touch

            def fast_existing_touch(self: Any, root: Path) -> Any:
                resolved = Path(root).expanduser().resolve()
                try:
                    data = self._read()
                    projects = [row for row in (data.get("projects") or []) if isinstance(row, dict)]
                    wanted = __import__("os").path.normcase(str(resolved))
                    for row in projects:
                        if __import__("os").path.normcase(str(row.get("root") or "")) != wanted:
                            continue
                        now = datetime.now(timezone.utc).isoformat()
                        row["lastOpenedUtc"] = now
                        rid = str(row.get("registryId") or self._registry_id(resolved))
                        data["activeProject"] = rid
                        self._write(data)
                        sc = row.get("sourceControl") if isinstance(row.get("sourceControl"), dict) else {}
                        gh = sc.get("github") if isinstance(sc.get("github"), dict) else {}
                        return RegisteredProject(
                            rid, str(row.get("projectId") or resolved.name),
                            str(row.get("name") or resolved.name), str(row.get("kind") or "project"),
                            resolved, now, str(gh.get("webUrl") or ""),
                        )
                except Exception:
                    pass
                return original_touch(self, resolved)

            ProjectRegistry.touch = fast_existing_touch
            ProjectRegistry._forge_fast_existing_touch_f564 = True
    except Exception:
        pass

    # Compact source status must never use the exact many-process implementation.
    try:
        from ForgeStatusCache import fast_source_status
        gui.forgepy_source_status = fast_source_status
    except Exception:
        pass


def install_class(cls: type[Any]) -> type[Any]:
    if getattr(cls, "_forge_performance_runtime_f564", False):
        return cls
    cls._forge_performance_runtime_f564 = True
    patch_module_aliases()

    original_shell = cls._build_shell
    original_census = getattr(cls, "_start_background_census", None)
    original_show_app = cls._show_app_tab

    def build_shell(self: Any) -> None:
        original_shell(self)
        self._forge_ui_lag_last = time.perf_counter()

        def heartbeat() -> None:
            try:
                now = time.perf_counter()
                last = float(getattr(self, "_forge_ui_lag_last", now))
                self._forge_ui_lag_last = now
                elapsed_ms = (now - last) * 1000.0
                lag_ms = max(0.0, elapsed_ms - 100.0)
                if lag_ms >= 80.0:
                    from ForgePerformance import record
                    record(
                        "ui-event-loop-lag",
                        lag_ms,
                        180.0,
                        {
                            "elapsedMs": round(elapsed_ms, 1),
                            "workspace": str(getattr(self, "_current_app_tab", "") or ""),
                            "project": str(getattr(getattr(self, "contract", None), "name", "") or ""),
                        },
                    )
            except Exception:
                pass
            try:
                self.window.after(100, heartbeat)
            except Exception:
                pass

        try:
            self.window.after(100, heartbeat)
            def ensure_application_layout() -> None:
                try:
                    from ForgeInstallLayout import ensure, resolve
                    self._forge_install_layout = ensure(resolve())
                except Exception:
                    pass
            self.window.after(250, ensure_application_layout)
            from pathlib import Path
            startup_root = Path(self.root_path).expanduser().resolve()
            from ForgeProjectInteractionPerformance import _background_hygiene, _background_project_audit
            self.window.after(7000, lambda root=startup_root: _background_hygiene(self, root))
            self.window.after(12000, lambda root=startup_root: _background_project_audit(self, root))
        except Exception:
            pass

    def show_app(self: Any, name: str) -> Any:
        COORDINATOR.mark_interaction()
        return original_show_app(self, name)

    if callable(original_census):
        def start_background_census(self: Any) -> None:
            # The baseline starts census five seconds after startup, exactly while an
            # operator is typically selecting the first project. Defer initial census.
            if not getattr(self, "_forge_census_initial_deferral", False):
                self._forge_census_initial_deferral = True
                try:
                    self.window.after(25000, self._start_background_census)
                except Exception:
                    pass
                return

            # Continue to yield while the operator is actively using the UI or while a
            # higher-value coordinated scan owns the disk lane.
            if COORDINATOR.interactive_recent(8.0) or COORDINATOR.scan_busy():
                try:
                    self.window.after(10000, self._start_background_census)
                except Exception:
                    pass
                return
            original_census(self)

        cls._start_background_census = start_background_census

    cls._build_shell = build_shell
    cls._show_app_tab = show_app
    cls._forge_load_coordinator = COORDINATOR
    return cls
