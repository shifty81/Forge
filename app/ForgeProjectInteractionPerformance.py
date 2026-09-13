#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ForgeLoadCoordinator import COORDINATOR
from ForgeStatusCache import fast_source_status

PROJECT_INTERACTION_VERSION = "FORGEPY-PROJECT-INTERACTION-1.1-F565"
_CACHE_LOCK = threading.RLock()
_REGISTRY_LOCK = threading.RLock()
_PREVIEW_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _cache_key(root: Path) -> str:
    return os.path.normcase(str(root.expanduser().resolve()))


def _cached_preview(root: Path, ttl: float = 20.0) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        item = _PREVIEW_CACHE.get(_cache_key(root))
    if item and time.monotonic() - item[0] <= ttl:
        return dict(item[1])
    return None


def _put_preview(root: Path, row: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _PREVIEW_CACHE[_cache_key(root)] = (time.monotonic(), dict(row))


def _github_details_from_status(source: dict[str, Any], fallback_web: str = "") -> dict[str, str]:
    declared_clone = str(source.get("githubDeclaredUrl") or "").strip()
    declared_web = str(source.get("githubDeclaredWebUrl") or fallback_web or "").strip()
    for row in source.get("remotes") or []:
        if str(row.get("kind") or "") != "github":
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        try:
            from ForgeProjectSource import normalize_github_repo
            clone, web = normalize_github_repo(url)
            return {"remote": str(row.get("name") or "origin"), "cloneUrl": clone, "webUrl": web}
        except Exception:
            try:
                from ForgeProjectSource import github_web_url_from_remote
                web = github_web_url_from_remote(url)
            except Exception:
                web = ""
            return {"remote": str(row.get("name") or "origin"), "cloneUrl": url, "webUrl": web or declared_web}
    return {"remote": "origin", "cloneUrl": declared_clone, "webUrl": declared_web}


def _github_from_status(source: dict[str, Any], fallback: str = "") -> str:
    return _github_details_from_status(source, fallback).get("webUrl", "")


def _forgegit_from_status(source: dict[str, Any]) -> str:
    for row in source.get("remotes") or []:
        name = str(row.get("name") or "").casefold()
        if name in {"forgegit", "internal", "internalgit"}:
            return "READY"
    return "NOT BOUND"


def _queued_updates(root: Path) -> int:
    try:
        from ForgePYIntake import counts_for_project
        data = counts_for_project(root) or {}
        return int(data.get("queued", 0) or data.get("QUEUED", 0) or 0)
    except Exception:
        return 0


def _preview(entry: Any, health: Any = None) -> dict[str, Any]:
    from PCCSurfaceCommon import BackendClient, ProjectContract
    from PCCVaultCatalog import latest_summary

    started = time.perf_counter()
    root = Path(entry.root).expanduser().resolve()
    contract = ProjectContract.load(root)
    backend = BackendClient(root, contract)
    catalog = latest_summary(root) or {}
    source = fast_source_status(root)
    capabilities: list[str] = []
    keys = {str(item.key) for item in contract.commands}
    if any(key.startswith("build") for key in keys):
        capabilities.append("Build")
    if any(key.startswith("gate.") for key in keys):
        capabilities.append("Gate")
    if any(key.startswith("test") for key in keys):
        capabilities.append("Test")
    if any(key.startswith("run.") for key in keys):
        capabilities.append("Run")
    row = {
        "project": contract.name,
        "kind": contract.kind,
        "root": str(root),
        "provider": backend.provider_label,
        "providerMode": backend.provider_mode,
        "discovery": str((contract.raw.get("_pccDiscovery") or {}).get("source") or "unknown"),
        "catalog": (
            f"{catalog.get('files', 0)} files / {catalog.get('duplicateGroups', 0)} duplicate groups"
            if catalog else "Not cataloged yet"
        ),
        "capabilities": ", ".join(capabilities) if capabilities else f"{len(contract.commands)} discovered command(s)",
        "health": getattr(health, "label", "") or "Background health pending",
        "github": _github_from_status(source, getattr(entry, "github_url", "")),
        "forgegit": _forgegit_from_status(source),
        "updates": _queued_updates(root),
        "branch": str(source.get("branch") or ""),
        "clean": bool(source.get("clean")),
        "elapsedMs": round((time.perf_counter() - started) * 1000.0, 1),
    }
    _put_preview(root, row)
    return row


def _render_preview(gui: Any, row: dict[str, Any]) -> None:
    try:
        clean = "CLEAN" if row.get("clean") else "DIRTY"
        gui.project_detail.configure(
            text=(
                f"Project    : {row.get('project','')}\n"
                f"Type       : {row.get('kind','')}\n"
                f"Root       : {row.get('root','')}\n"
                f"Health     : {row.get('health','')}\n"
                f"Provider   : {row.get('provider','')} ({row.get('providerMode','')})\n"
                f"Discovery  : {row.get('discovery','')}\n"
                f"Capabilities: {row.get('capabilities','')}\n"
                f"Source     : {row.get('branch','-')} · {clean}\n"
                f"ForgeGit   : {row.get('forgegit','NOT BOUND')}\n"
                f"GitHub     : {row.get('github','Not configured')}\n"
                f"Updates    : {row.get('updates',0)} queued\n"
                f"Vault      : {row.get('catalog','')}"
            ),
            fg="#edf2f5",
        )
    except Exception:
        pass


def _render_preview_loading(gui: Any, entry: Any) -> None:
    try:
        health = gui._project_health_cache.get(entry.registry_id)
        health_line = getattr(health, "label", "Background health pending") if health is not None else "Background health pending"
        gui.project_detail.configure(
            text=(
                f"Project    : {entry.name}\n"
                f"Type       : {entry.kind}\n"
                f"Root       : {entry.root}\n"
                f"Health     : {health_line}\n"
                "Provider   : Loading project metadata…\n"
                "Source     : Loading in background…"
            ),
            fg="#929aa3",
        )
    except Exception:
        pass


def _registry_touch_preloaded(registry: Any, root: Path, contract: Any, source: dict[str, Any]) -> tuple[str, str]:
    """Mark active with already-discovered metadata, with a safe public fallback.

    The fast path avoids a second project discovery/Git probe. If a future/local
    ProjectRegistry implementation changes its private storage shape, fall back to
    the stable public touch() API in the worker rather than leaving activeProject stale.
    """
    warning = ""
    with _REGISTRY_LOCK:
        try:
            from ForgePYPaths import projects_root
            now = datetime.now(timezone.utc).isoformat()
            rid = registry._registry_id(root)
            data = registry._read()
            projects = [item for item in (data.get("projects") or []) if isinstance(item, dict)]
            try:
                portable = root.relative_to(projects_root().resolve()).as_posix()
            except Exception:
                portable = ""
            github = _github_details_from_status(source, "")
            record = {
                "registryId": rid,
                "projectId": contract.project_id,
                "name": contract.name,
                "kind": contract.kind,
                "root": str(root),
                "portablePath": portable,
                "sourceControl": {"github": github},
                "lastOpenedUtc": now,
            }
            found = False
            for index, item in enumerate(projects):
                same_portable = bool(portable) and str(item.get("portablePath") or "").casefold() == portable.casefold()
                same = (
                    str(item.get("registryId") or "") == rid
                    or os.path.normcase(str(item.get("root") or "")) == os.path.normcase(str(root))
                    or same_portable
                )
                if same:
                    record["registryId"] = str(item.get("registryId") or rid)
                    rid = record["registryId"]
                    projects[index] = record
                    found = True
                    break
            if not found:
                projects.append(record)
            data["projects"] = projects
            data["activeProject"] = rid
            registry._write(data)

            discovery = contract.raw.get("_pccDiscovery") or {}
            payload = {
                "schema": "FORGE_PROJECT_PASSPORT_V1",
                "projectId": contract.project_id,
                "name": contract.name,
                "kind": contract.kind,
                "root": str(root),
                "trustState": "trusted_local",
                "integrationState": "auto_bound" if contract.commands else "observed",
                "contractSource": str(discovery.get("source") or "filesystem-scan"),
                "projectContractRequired": False,
                "provider": str(discovery.get("provider") or (contract.raw.get("root_control_center") or {}).get("machine_provider") or ""),
                "capabilities": sorted({item.category for item in contract.commands if item.category}),
                "commands": [item.key for item in contract.commands],
                "qualityGates": list(contract.gate_keys),
                "markers": discovery.get("markers") or {},
                "sourceControl": {"github": github},
                "lastOpenedUtc": now,
                "updatedUtc": now,
            }
            path = registry.passport_path(root)
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.replace(temp, path)
            return rid, ""
        except Exception as exc:
            warning = f"preloaded registry fast path unavailable ({exc}); used public registry fallback"

        try:
            entry = registry.touch(root)
            return str(getattr(entry, "registry_id", "") or ""), warning
        except Exception as exc:
            return "", warning + f"; public registry fallback failed: {exc}"


def _background_hygiene(gui: Any, root: Path) -> None:
    root = root.expanduser().resolve()
    root_key = _cache_key(root)
    generation = int(getattr(gui, "_forge_hygiene_generation", 0) or 0) + 1
    gui._forge_hygiene_generation = generation
    if not hasattr(gui, "_forge_hygiene_results"):
        gui._forge_hygiene_results = {}

    def work() -> None:
        try:
            from PCCRepoHygiene import prepare
            result = COORDINATOR.run_scan(
                f"repo-hygiene:{root.name}",
                lambda: prepare(root, apply=True),
                wait_for_idle=2.0,
            )
            payload = (True, result)
        except Exception as exc:
            payload = (False, str(exc))
        gui._forge_hygiene_results[(generation, root_key)] = payload

    def poll(attempts: int = 600) -> None:
        token = (generation, root_key)
        result = getattr(gui, "_forge_hygiene_results", {}).pop(token, None)
        if result is None:
            if attempts > 0:
                gui.window.after(100, lambda: poll(attempts - 1))
            return
        # Hygiene may safely finish for the old project, but stale results must not
        # alter the currently selected project's visible status/log narrative.
        if _cache_key(Path(gui.root_path)) != root_key:
            return
        ok, payload = result
        try:
            if ok:
                moved = int((payload or {}).get("moved", 0) or 0)
                gui._append_log(f"[PASS] Background project hygiene complete: {moved} transport artifact(s) moved.\n", "pass")
            else:
                gui._append_log(f"[WARN] Background project hygiene: {payload}\n", "warn")
        except Exception:
            pass

    threading.Thread(target=work, daemon=True, name="ForgeProjectHygiene").start()
    gui.window.after(100, poll)


def _background_project_audit(gui: Any, root: Path) -> None:
    """Refresh the two project handoffs only when missing/stale."""
    root = root.expanduser().resolve()
    root_key = _cache_key(root)
    generation = int(getattr(gui, "_forge_handoff_generation", 0) or 0) + 1
    gui._forge_handoff_generation = generation
    if not hasattr(gui, "_forge_handoff_results"):
        gui._forge_handoff_results = {}

    def work() -> None:
        try:
            from ForgeProjectAudit import handoffs_need_refresh, write_handoffs
            if not handoffs_need_refresh(root):
                payload = (True, None, "CURRENT")
            else:
                result = COORDINATOR.run_scan(
                    f"project-handoff:{root.name}",
                    lambda: write_handoffs(root, deep=False),
                    wait_for_idle=3.0,
                )
                payload = (True, result, "REFRESHED")
        except Exception as exc:
            payload = (False, str(exc), "FAILED")
        gui._forge_handoff_results[(generation, root_key)] = payload

    def poll(attempts: int = 1200) -> None:
        token = (generation, root_key)
        result = getattr(gui, "_forge_handoff_results", {}).pop(token, None)
        if result is None:
            if attempts > 0:
                gui.window.after(100, lambda: poll(attempts - 1))
            return
        if _cache_key(Path(gui.root_path)) != root_key:
            return
        ok, payload, state = result
        try:
            if ok and state == "REFRESHED":
                gui._append_log("[PASS] ForgePY project support/integration handoffs refreshed.\n", "pass")
            elif not ok:
                gui._append_log(f"[WARN] Project integration handoff refresh: {payload}\n", "warn")
        except Exception:
            pass

    threading.Thread(target=work, daemon=True, name="ForgeProjectHandoffRefresh").start()
    gui.window.after(100, poll)


def install(cls: type[Any]) -> type[Any]:
    if getattr(cls, "_forge_project_interaction_f565", False):
        return cls
    cls._forge_project_interaction_f565 = True

    original_show_app = cls._show_app_tab
    original_show_page = cls._show_page

    def project_selection_changed(self: Any, _event: Any = None) -> None:
        entry = self._selected_project()
        if entry is None:
            try:
                self.project_detail.configure(text="Select a registered project.", fg="#929aa3")
            except Exception:
                pass
            return
        COORDINATOR.mark_interaction()
        generation = int(getattr(self, "_forge_preview_generation", 0) or 0) + 1
        self._forge_preview_generation = generation
        _render_preview_loading(self, entry)
        cached = _cached_preview(Path(entry.root))
        if cached is not None:
            _render_preview(self, cached)
            return

        def begin() -> None:
            if generation != int(getattr(self, "_forge_preview_generation", 0) or 0):
                return
            health = self._project_health_cache.get(entry.registry_id)
            if not hasattr(self, "_forge_preview_results"):
                self._forge_preview_results = {}

            def worker() -> None:
                try:
                    row = _preview(entry, health)
                    self._forge_preview_results[generation] = (generation, True, row)
                except Exception as exc:
                    self._forge_preview_results[generation] = (generation, False, str(exc))

            def poll(attempts: int = 400) -> None:
                result = getattr(self, "_forge_preview_results", {}).pop(generation, None)
                if result is None:
                    if attempts > 0:
                        self.window.after(25, lambda: poll(attempts - 1))
                    return
                result_generation, ok, payload = result
                if result_generation != int(getattr(self, "_forge_preview_generation", 0) or 0):
                    return
                if ok:
                    _render_preview(self, payload)
                else:
                    try:
                        self.project_detail.configure(text=f"{entry.name}\n\nPreview scan needs attention: {payload}", fg="#ffd44a")
                    except Exception:
                        pass

            threading.Thread(target=worker, daemon=True, name="ForgeProjectPreview").start()
            self.window.after(25, poll)

        self.window.after(120, begin)

    def activate_project(self: Any, root: Path) -> None:
        if getattr(self, "_busy", False):
            try:
                self._popup("ForgePY", "Finish or stop the active Forge job before switching projects.", kind="warning")
            except Exception:
                pass
            return
        target = Path(root).expanduser().resolve()
        if target == Path(self.root_path).resolve() and getattr(self, "backend", None) is not None:
            callback = getattr(self, "_forge_activation_success_callback", None)
            self._forge_activation_success_callback = None
            if callable(callback):
                callback()
            return
        if getattr(self, "_forge_project_activation_running", False):
            try:
                self._append_log("[INFO] Project switch already in progress.\n", "info")
            except Exception:
                pass
            return

        COORDINATOR.mark_interaction()
        self._forge_project_activation_running = True
        generation = int(getattr(self, "_forge_activation_generation", 0) or 0) + 1
        self._forge_activation_generation = generation
        if not hasattr(self, "_forge_activation_results"):
            self._forge_activation_results = {}
        try:
            self.project_detail.configure(text=f"Opening {target.name}…\n\nProject discovery is running in the background.", fg="#929aa3")
        except Exception:
            pass
        started = time.perf_counter()
        target_key = _cache_key(target)

        def worker() -> None:
            with COORDINATOR.interactive("project-activation"):
                try:
                    from PCCSurfaceCommon import BackendClient, ProjectContract, SurfaceError
                    contract = ProjectContract.load(target)
                    backend = None
                    backend_error = ""
                    try:
                        backend = BackendClient(target, contract)
                    except SurfaceError as exc:
                        backend_error = str(exc)
                    except Exception as exc:
                        backend_error = str(exc)
                    source = fast_source_status(target, force=True)
                    rid, registry_warning = _registry_touch_preloaded(self.registry, target, contract, source)
                    payload = (generation, True, contract, backend, backend_error, source, rid, registry_warning)
                except Exception as exc:
                    payload = (generation, False, str(exc))
                self._forge_activation_results[(generation, target_key)] = payload

        def poll(attempts: int = 1200) -> None:
            token = (generation, target_key)
            result = getattr(self, "_forge_activation_results", {}).pop(token, None)
            if result is None:
                if attempts > 0:
                    self.window.after(25, lambda: poll(attempts - 1))
                else:
                    self._forge_project_activation_running = False
                    try:
                        self._popup("Open Project", "Project activation timed out. The current project was left unchanged.", kind="warning")
                    except Exception:
                        pass
                return
            if result[0] != generation:
                return
            self._forge_project_activation_running = False
            if not result[1]:
                try:
                    self._popup("Unable to Load Project", f"{target}\n\n{result[2]}", kind="error")
                except Exception:
                    pass
                return

            _, _, contract, backend, backend_error, _source, _rid, registry_warning = result
            self.root_path = target
            self.contract = contract
            self.backend = backend
            self.backend_error = backend_error
            self._last_status = {}
            try:
                self._update_header()
            except Exception:
                pass
            try:
                self._reset_status_cards()
            except Exception:
                pass
            try:
                self._clear_log()
            except Exception:
                pass
            try:
                from ForgeWorkspaceSurface import invalidate as invalidate_workspace
                invalidate_workspace(self)
            except Exception:
                pass
            try:
                self._append_log(f"[PASS] Active project changed to {contract.name}.\n", "pass")
                self._append_log(f"Root: {target}\n", "muted")
                if registry_warning:
                    self._append_log(f"[WARN] Registry/passport refresh: {registry_warning}\n", "warn")
                if backend_error:
                    self._append_log(f"[WARN] Project provider: {backend_error}\n", "warn")
            except Exception:
                pass
            try:
                if hasattr(self, "_forge_render_context_quickbar"):
                    self._forge_render_context_quickbar()
            except Exception:
                pass
            try:
                from ForgePerformance import record
                record("project.activate", (time.perf_counter() - started) * 1000.0, 350.0, {"project": contract.name})
            except Exception:
                pass

            callback = getattr(self, "_forge_activation_success_callback", None)
            self._forge_activation_success_callback = None
            if callable(callback):
                try:
                    callback()
                except Exception:
                    pass

            def finish_secondary_ui() -> None:
                try:
                    self._reload_registered_commands()
                except Exception:
                    pass
                try:
                    self._refresh_console_command_catalog()
                except Exception:
                    pass

            self.window.after(1, finish_secondary_ui)
            self.window.after(30, self._refresh_status_async)
            self.window.after(900, lambda: _background_hygiene(self, target))
            self.window.after(1600, lambda: _background_project_audit(self, target))

        threading.Thread(target=worker, daemon=True, name="ForgeProjectActivate").start()
        self.window.after(25, poll)

    def open_selected_project(self: Any) -> None:
        entry = self._selected_project()
        if entry is None:
            try:
                self._popup("Vault", "Select a project first.", kind="info")
            except Exception:
                pass
            return

        def after() -> None:
            try:
                original_show_page(self, "Dashboard")
            except Exception:
                pass
            try:
                original_show_app(self, "Project Workspace")
            except Exception:
                pass
            self._current_app_tab = "Project Workspace"
            try:
                from ForgeUnifiedWorkflow import _set_top_nav_active
                _set_top_nav_active(self, "Project")
            except Exception:
                pass
            try:
                if hasattr(self, "_forge_render_context_quickbar"):
                    self._forge_render_context_quickbar()
            except Exception:
                pass

        self._forge_activation_success_callback = after
        activate_project(self, entry.root)

    cls._project_selection_changed = project_selection_changed
    cls._activate_project = activate_project
    cls._open_selected_project = open_selected_project
    return cls
