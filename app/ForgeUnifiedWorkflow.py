#!/usr/bin/env python3
from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

WORKFLOW_VERSION = "FORGEPY-UNIFIED-WORKFLOW-F743"


def _safe_log(gui: Any, text: str, tag: str = "info") -> None:
    try:
        gui._append_log(text.rstrip("\n") + "\n", tag)
    except Exception:
        pass


def _queue_resolved_patch(gui: Any, module: Any, source: Path, target_root: Path) -> None:
    target_root = Path(target_root).expanduser().resolve()
    token = uuid.uuid4().hex
    if not hasattr(gui, "_forge_queue_results"):
        gui._forge_queue_results = {}

    def worker() -> None:
        try:
            from ForgePYIntake import queue_patch_to_project
            payload = queue_patch_to_project(target_root, source)
            gui._forge_queue_results[token] = (True, payload)
        except Exception as exc:
            gui._forge_queue_results[token] = (False, str(exc))

    def poll(attempts: int = 120) -> None:
        result = getattr(gui, "_forge_queue_results", {}).pop(token, None)
        if result is None:
            if attempts <= 0:
                gui._popup("Queue Patch", "Timed out while queueing the patch. Project source was not changed.", kind="warning")
                return
            gui.window.after(250, lambda: poll(attempts - 1))
            return
        ok, payload = result
        if not ok:
            gui._popup("Queue Patch", f"Patch could not be queued:\n{payload}", kind="error")
            return
        name = str((payload or {}).get("patch_id") or source.name)
        _safe_log(gui, f"[PASS] Queued update {name} for {target_root}; project source is unchanged.", "pass")
        gui._popup(
            "Update Queued",
            f"{source.name}\n\nQueued for: {target_root.name}\n\n"
            "Nothing was applied. Open that project's Dashboard / Updates surface when you are ready to apply and certify it.",
            kind="success",
        )
        try:
            gui._refresh_status_async()
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True, name="ForgeQueuePatch").start()
    gui.window.after(250, poll)



def _audit_registered_projects_async(gui: Any) -> None:
    """Refresh project audits serially without ever touching Tk from a worker."""
    if getattr(gui, "_forge_registered_audit_running", False):
        return
    gui._forge_registered_audit_running = True
    gui._forge_registered_audit_result = None

    try:
        entries = list(gui.registry.entries() or [])
    except Exception:
        entries = []

    def worker() -> None:
        passed = 0
        failures: list[str] = []
        try:
            from ForgeProjectAudit import handoffs_need_refresh, write_handoffs
            for entry in entries:
                try:
                    root = Path(entry.root).expanduser().resolve()
                    if not root.is_dir():
                        continue
                    if not handoffs_need_refresh(root):
                        continue
                    from ForgeLoadCoordinator import COORDINATOR
                    COORDINATOR.run_scan(
                        f"project-audit:{root.name}",
                        lambda root=root: write_handoffs(root, deep=False),
                        wait_for_idle=3.0,
                    )
                    passed += 1
                except Exception as exc:
                    failures.append(f"{getattr(entry, 'name', entry.root)}: {exc}")
        except Exception as exc:
            failures.append(str(exc))
        gui._forge_registered_audit_result = (passed, failures)

    def poll(attempts: int = 1200) -> None:
        result = getattr(gui, "_forge_registered_audit_result", None)
        if result is None:
            if attempts > 0:
                gui.window.after(250, lambda: poll(attempts - 1))
            else:
                gui._forge_registered_audit_running = False
                _safe_log(gui, "[WARN] Background project intake audit exceeded the UI wait window.", "warn")
            return
        gui._forge_registered_audit_result = None
        gui._forge_registered_audit_running = False
        passed, failures = result
        for failure in failures[:8]:
            _safe_log(gui, f"[WARN] Project intake audit: {failure}", "warn")
        if len(failures) > 8:
            _safe_log(gui, f"[WARN] Project intake audit: {len(failures) - 8} additional project(s) need attention.", "warn")
        _safe_log(
            gui,
            f"[PASS] Project intake audit refreshed {passed} project handoff set(s); {len(failures)} need attention.",
            "pass" if not failures else "warn",
        )

    threading.Thread(target=worker, daemon=True, name="ForgeRegisteredProjectAudit").start()
    gui.window.after(250, poll)

def _walk_widgets(widget: Any):
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk_widgets(child)


def _widget_text(widget: Any) -> str:
    try:
        return str(widget.cget("text") or "")
    except Exception:
        return ""


def _hide_named_buttons(root: Any, names: set[str]) -> None:
    wanted = {x.casefold().strip() for x in names}
    for widget in _walk_widgets(root):
        if _widget_text(widget).casefold().strip() not in wanted:
            continue
        try:
            if widget.winfo_class() not in {"Button", "TButton"}:
                continue
        except Exception:
            pass
        try:
            widget.pack_forget()
        except Exception:
            try:
                widget.grid_remove()
            except Exception:
                pass


def _rename_widget_text(root: Any, mapping: dict[str, str]) -> None:
    folded = {k.casefold().strip(): v for k, v in mapping.items()}
    for widget in _walk_widgets(root):
        current = _widget_text(widget)
        replacement = folded.get(current.casefold().strip())
        if replacement is None:
            continue
        try:
            widget.configure(text=replacement)
        except Exception:
            pass


def _selected_project_entry(gui: Any) -> Any | None:
    try:
        if hasattr(gui, "_selected_project"):
            return gui._selected_project()
    except Exception:
        pass
    try:
        selection = list(gui.projects_tree.selection() or [])
        if not selection:
            return None
        return gui._project_entries_by_id.get(selection[0])
    except Exception:
        return None


def _audit_selected_project(gui: Any) -> None:
    entry = _selected_project_entry(gui)
    if entry is None:
        gui._popup("Vault", "Select a project first.", kind="info")
        return
    root = Path(entry.root).expanduser().resolve()
    if getattr(gui, "_forge_single_project_audit_running", False):
        gui._popup("Project Audit", "A project audit is already running.", kind="info")
        return
    gui._forge_single_project_audit_running = True
    _safe_log(gui, f"[INFO] Auditing {entry.name} for ForgePY support and project integration.", "info")

    def worker() -> None:
        try:
            from ForgeProjectAudit import write_handoffs
            from ForgeLoadCoordinator import COORDINATOR
            result = COORDINATOR.run_scan(
                f"project-audit:{root.name}",
                lambda: write_handoffs(root, deep=False),
                wait_for_idle=1.0,
            )
            gui._forge_single_project_audit_result = (True, result)
        except Exception as exc:
            gui._forge_single_project_audit_result = (False, str(exc))

    def poll(attempts: int = 240) -> None:
        result = getattr(gui, "_forge_single_project_audit_result", None)
        if result is None:
            if attempts > 0:
                gui.window.after(250, lambda: poll(attempts - 1))
            else:
                gui._forge_single_project_audit_running = False
                gui._popup("Project Audit", "Audit timed out. No project source was changed.", kind="warning")
            return
        gui._forge_single_project_audit_result = None
        gui._forge_single_project_audit_running = False
        ok, payload = result
        if not ok:
            gui._popup("Project Audit", f"Audit failed:\n{payload}", kind="error")
            return
        audit = dict(payload.get("audit") or {})
        grade = str((audit.get("protocol") or {}).get("grade") or "AUDITED")
        _safe_log(gui, f"[PASS] {entry.name} audit complete: {grade}.", "pass")
        gui._popup(
            "Project Audit Complete",
            f"{entry.name}\n\nIntegration grade: {grade}\n\n"
            "ForgePY Support Handoff and Project Integration Handoff were refreshed in Artifact Central.",
            kind="success",
        )
        try:
            gui._refresh_projects()
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True, name="ForgeSelectedProjectAudit").start()
    gui.window.after(250, poll)


def _show_vault_projects(gui: Any, original_show_app: Any) -> None:
    original_show_app(gui, "Projects")
    gui._current_app_tab = "Vault"
    gui._forge_vault_view = "Projects"
    _set_top_nav_active(gui, "Vault")
    try:
        gui._forge_render_context_quickbar()
    except Exception:
        pass


def _show_vault_library(gui: Any, original_show_app: Any) -> None:
    original_show_app(gui, "Vault")
    gui._current_app_tab = "Vault"
    gui._forge_vault_view = "Library"
    _set_top_nav_active(gui, "Vault")
    try:
        gui._forge_render_context_quickbar()
    except Exception:
        pass


def _set_top_nav_active(gui: Any, active: str) -> None:
    for key, btn in getattr(gui, "_app_tab_buttons", {}).items():
        if key in {"Projects", "Source Control", "Cortex"}:
            continue
        try:
            is_active = (
                (active == "Vault" and key == "Vault")
                or (active == "Project" and key == "Project Workspace")
                or (active == "Workspace" and key == "IDE")
                or (active == "Settings" and key == "Settings")
            )
            btn.configure(
                bg="#171c22" if is_active else "#11151a",
                fg="#00d9ff" if is_active else "#edf2f5",
            )
        except Exception:
            pass



def _start_canonical(gui: Any, canonical: str) -> None:
    """GUI adapter into the same canonical command vocabulary used by CLI/Cortex."""
    try:
        from ForgeProjectProtocol import provider_command
        gui._start_command(provider_command(canonical))
    except Exception:
        gui._start_command(canonical)


def _hide_legacy_workspace_settings(gui: Any) -> None:
    """Remove deprecated Monaco/pywebview rows without orphaning entry controls."""
    try:
        from ForgeUiWorkflowModel import LEGACY_WORKSPACE_BUTTONS
        _hide_named_buttons(gui.window, set(LEGACY_WORKSPACE_BUTTONS))
    except Exception:
        pass

    def hide(widget: Any) -> None:
        target = widget
        try:
            parent = widget.master
            if parent is not None and parent is not gui.window and parent.winfo_class() in {"Frame", "TFrame"}:
                children = list(parent.winfo_children())
                if 1 <= len(children) <= 8:
                    target = parent
        except Exception:
            target = widget
        try:
            target.pack_forget()
        except Exception:
            try:
                target.grid_remove()
            except Exception:
                pass

    for widget in list(_walk_widgets(gui.window)):
        text = _widget_text(widget).casefold()
        if text and ("monaco" in text or "pywebview" in text):
            hide(widget)


def _normalize_project_content(gui: Any) -> None:
    """Dashboard is summary/context; context quick bar owns normal Build/Run actions."""
    frame = getattr(gui, "_app_frames", {}).get("Project Workspace")
    if frame is None:
        return
    try:
        from ForgeUiWorkflowModel import PROJECT_NAV_HIDDEN
        _hide_named_buttons(frame, set(PROJECT_NAV_HIDDEN))
    except Exception:
        _hide_named_buttons(frame, {"Build & Run"})
    # Do not recursively hide command buttons across Advanced pages. The duplicate
    # workflow is the legacy Build & Run navigation page, not the underlying
    # project-owned command capability.
    try:
        _rename_widget_text(frame, {"Tooling": "Project Tools", "Advanced Commands": "Advanced"})
    except Exception:
        pass

    # SimplifiedUX historically inserted verified project-tool category buttons into the
    # primary app rail. Keep the primary rail exactly Vault/Project/Workspace/Settings.
    host = getattr(gui, "_forge_project_tool_host", None)
    if host is not None:
        try:
            host.pack_forget()
        except Exception:
            pass

def _normalize_user_facing_terms(gui: Any) -> None:
    try:
        from ForgeUiWorkflowModel import USER_FACING_RENAMES
        _rename_widget_text(gui.window, dict(USER_FACING_RENAMES))
    except Exception:
        pass
    # Patch intake remains owned by the compact right-side project/health rail.
    # Do not recreate picker buttons in the quick bar; the rail control and global
    # drag/drop both route into the same queue-only intake authority.
    _hide_legacy_workspace_settings(gui)
    _normalize_project_content(gui)

def _normalize_left_navigation(gui: Any) -> None:
    """Leave exactly Vault / Project / Workspace / Settings in the primary rail."""
    host = getattr(gui, "app_nav_host", None)
    if host is None:
        return

    # SimplifiedUX/local candidate builds may have inserted Operations/Updates buttons
    # outside _app_tab_buttons. Remove them by presentation text as well.
    try:
        from ForgeUiWorkflowModel import LEGACY_TOP_LEVEL_HIDDEN
        hidden = set(LEGACY_TOP_LEVEL_HIDDEN)
    except Exception:
        hidden = {"Operations", "Updates", "Projects", "Source Control", "Cortex", "Dashboard"}
    _hide_named_buttons(host, hidden)

    buttons = getattr(gui, "_app_tab_buttons", {})
    try:
        from ForgeUiWorkflowModel import primary_bindings
        labels = primary_bindings()
    except Exception:
        labels = {"Vault": "Vault", "Project Workspace": "Project", "IDE": "Workspace", "Settings": "Settings"}
    for key in ("Projects", "Source Control", "Cortex"):
        try:
            buttons[key].pack_forget()
        except Exception:
            pass

    # Repack the four surviving navigation buttons directly after the header.
    for key in ("Vault", "Project Workspace", "IDE", "Settings"):
        btn = buttons.get(key)
        if btn is None:
            continue
        try:
            btn.configure(text=labels[key])
            btn.pack_forget()
            btn.pack(fill="x", padx=5, pady=1)
        except Exception:
            pass

    try:
        gui.app_nav_title.configure(text="FORGEPY")
    except Exception:
        pass


def _normalize_vault_projects_content(gui: Any, parent: Any) -> None:
    """Turn the legacy Projects page into the actionable Vault home."""
    _rename_widget_text(
        parent,
        {
            "Registered Projects": "Vault Projects",
            "Register Local...": "Add Local Project...",
            "Open Workspace": "Open Project",
        },
    )
    # Project operations live in the contextual quick bar; remove the duplicate row.
    _hide_named_buttons(
        parent,
        {
            "Register Local...", "Add Local Project...", "Clone GitHub...",
            "Open Workspace", "Open Project",
        },
    )

    # Add a concise workflow hint at the top without creating another button wall.
    try:
        tk = gui.tk
        banner = tk.Frame(parent, bg="#11151a", highlightthickness=1, highlightbackground="#28313a")
        banner.pack(fill="x", padx=20, pady=(12, 0), before=parent.winfo_children()[0] if parent.winfo_children() else None)
        tk.Label(
            banner,
            text="VAULT",
            bg="#11151a", fg="#00d9ff", font=("Segoe UI Semibold", 10), anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 1))
        tk.Label(
            banner,
            text="Choose a project, audit it for ForgePY compatibility, then open its Project Dashboard. "
                 "Use Library only for deep catalog/lineage inspection.",
            bg="#11151a", fg="#929aa3", font=("Segoe UI", 9), anchor="w", justify="left",
        ).pack(fill="x", padx=12, pady=(0, 8))
    except Exception:
        pass


def _open_selected_project_dashboard(gui: Any, original_open: Any, original_show_app: Any) -> None:
    entry = _selected_project_entry(gui)
    if entry is None:
        gui._popup("Vault", "Select a project first.", kind="info")
        return
    original_open(gui)
    try:
        gui._show_page("Dashboard")
    except Exception:
        pass
    original_show_app(gui, "Project Workspace")
    gui._current_app_tab = "Project Workspace"
    gui._forge_vault_view = "Projects"
    _set_top_nav_active(gui, "Project")
    try:
        gui._forge_render_context_quickbar()
    except Exception:
        pass


def _install_async_workspace_refresh(cls: type[Any]) -> None:
    """Install the F520 lightweight/lazy native Workspace surface."""
    if getattr(cls, "_forge_workspace_surface_f520_installed", False):
        return
    from ForgeWorkspaceSurface import (
        build as workspace_build,
        refresh_files as workspace_refresh,
        selection_changed as workspace_selection_changed,
        save_current as workspace_save,
    )
    cls._build_ide_tab = workspace_build
    cls._ide_refresh_files = workspace_refresh
    cls._ide_selection_changed = workspace_selection_changed
    cls._ide_save_native = workspace_save
    cls._forge_workspace_surface_f520_installed = True


def _prebuild_workspace_shell(gui: Any) -> None:
    """Build only the cheap Workspace widgets during idle time; perform no scan."""
    if "IDE" in getattr(gui, "_built_app_tabs", set()):
        return
    builder = getattr(gui, "_lazy_app_builders", {}).get("IDE")
    frame = getattr(gui, "_app_frames", {}).get("IDE")
    if builder is None or frame is None:
        return
    try:
        builder(frame)
        gui._built_app_tabs.add("IDE")
    except Exception as exc:
        _safe_log(gui, f"[WARN] Workspace shell warmup deferred: {exc}", "warn")


def _refresh_visible_identity(gui: Any) -> None:
    try:
        from ForgeApplicationIdentity import normalize_gui
        normalize_gui(gui)
    except Exception:
        pass
    try:
        from ForgeProjectIdentity import label
        value=label(Path(gui.root_path))
        if hasattr(gui,"_forge_status_project"):
            gui._forge_status_project.configure(text=value)
        if hasattr(gui,"_forge_quick_project"):
            gui._forge_quick_project.configure(text=value)
    except Exception:
        pass

def _normalize_surface_once(gui: Any, key: str) -> None:
    done=set(getattr(gui,"_forge_normalized_surfaces",set()) or set())
    if key in done:
        _refresh_visible_identity(gui)
        return
    frame=(getattr(gui,"_app_frames",{}) or {}).get(key)
    if frame is not None:
        try:
            from ForgeUiWorkflowModel import USER_FACING_RENAMES
            _rename_widget_text(frame,dict(USER_FACING_RENAMES))
        except Exception:
            pass
        if key == "Project Workspace":
            try:
                _normalize_project_content(gui)
            except Exception:
                pass
        elif key == "Settings":
            try:
                _hide_legacy_workspace_settings(gui)
            except Exception:
                pass
    done.add(key)
    gui._forge_normalized_surfaces=done
    _refresh_visible_identity(gui)

def patch_simplified_ux(module: Any) -> None:
    if getattr(module, "_forge_f485_workflow_patch", False):
        return
    module._forge_f485_workflow_patch = True

    # ------------------------------------------------------------------
    # Queue-only picker/drop behavior
    # ------------------------------------------------------------------
    def present_patch_resolution(gui: Any, source: Path, resolution: dict[str, Any]) -> None:
        status = str(resolution.get("status") or "").upper()
        if status == "RESOLVED":
            target_root = Path(str(resolution.get("targetRoot") or "")).expanduser().resolve()
            target_name = str(resolution.get("targetProject") or target_root.name)
            current = Path(gui.root_path).resolve()
            note = "" if current == target_root else f"\n\nCurrent workspace: {gui.contract.name}. The queue will belong to {target_name}; the visible workspace will not switch."
            if gui._popup(
                "Queue Patch",
                f"{source.name}\n\nTarget: {target_name}\nCompatibility: READY{note}\n\n"
                "Queue this update for the project?\n\nNo project files will be changed.",
                kind="success",
                confirm=True,
            ):
                _queue_resolved_patch(gui, module, source, target_root)
            return
        if status == "AMBIGUOUS":
            # Preserve the mature target chooser, but its final approval call is replaced
            # below with queue-only behavior.
            module._choose_ambiguous_project(gui, source, list(resolution.get("matches") or []))
            return
        reason = str(resolution.get("reason") or resolution.get("error") or "Patch does not currently apply to a registered project.")
        gui._popup("Patch Intake", f"{source.name}\n\n{reason}\n\nForgePY left the file untouched.", kind="warning")

    def approve_manual_and_queue(gui: Any, source: Path, target_root: Path) -> None:
        _queue_resolved_patch(gui, module, source, target_root)

    def present_updates(gui: Any, ready: list[dict[str, Any]], review: list[dict[str, Any]]) -> None:
        current = str(getattr(gui.contract, "project_id", "") or "").casefold()
        current_name = str(getattr(gui.contract, "name", "") or "").casefold()
        relevant = [item for item in ready if str(item.get("target_project") or "").casefold() in {current, current_name}]
        if relevant:
            item = relevant[0]
            name = str(item.get("source_name") or item.get("patch_id") or "Update")
            intake_id = str(item.get("intake_id") or "")
            if gui._popup(
                "Update Ready",
                f"{name}\n\nCompatible with {gui.contract.name}.\n\nQueue it for this project?\n\n"
                "The project will not be modified until Apply Updates is selected from its Dashboard.",
                kind="success",
                confirm=True,
            ):
                token = uuid.uuid4().hex
                if not hasattr(gui, "_forge_queue_candidate_results"):
                    gui._forge_queue_candidate_results = {}
                def worker() -> None:
                    try:
                        from ForgePYIntake import approve_available_globally
                        approved = approve_available_globally(intake_id)
                        gui._forge_queue_candidate_results[token] = (True, approved)
                    except Exception as exc:
                        gui._forge_queue_candidate_results[token] = (False, str(exc))
                def poll(attempts: int = 120) -> None:
                    result = getattr(gui, "_forge_queue_candidate_results", {}).pop(token, None)
                    if result is None:
                        if attempts > 0:
                            gui.window.after(250, lambda: poll(attempts - 1))
                        return
                    ok, payload = result
                    if ok:
                        gui._popup("Update Queued", f"{name}\n\nQueued for {gui.contract.name}. Nothing was applied.", kind="success")
                        _safe_log(gui, f"[PASS] Queued {name} for {gui.contract.name}; source unchanged.", "pass")
                    else:
                        gui._popup("Queue Update", f"Could not queue update:\n{payload}", kind="error")
                threading.Thread(target=worker, daemon=True, name="ForgeQueueCandidate").start()
                gui.window.after(250, poll)
            return
        review_current = [item for item in review if str(item.get("target_project") or "").casefold() in {current, current_name}]
        if review_current:
            gui._popup("Update Needs Attention", f"{len(review_current)} update(s) need review for {gui.contract.name}.", kind="warning")
            return
        gui._popup("Updates", f"No actionable update is ready for {gui.contract.name}.", kind="info")

    module._present_patch_resolution = present_patch_resolution
    module._approve_manual_and_gate = approve_manual_and_queue
    module._present_updates = present_updates

    # ------------------------------------------------------------------
    # Post-install class normalization
    # ------------------------------------------------------------------
    original_install = module.install_forge_gui

    def install_forge_gui(cls: type[Any]) -> type[Any]:
        cls = original_install(cls)
        _install_async_workspace_refresh(cls)
        if getattr(cls, "_forge_f740_unified_shell_installed", False):
            return cls
        cls._forge_f740_unified_shell_installed = True

        original_shell = cls._build_shell
        original_show_app = cls._show_app_tab
        original_show_page = cls._show_page
        original_activate = cls._activate_project
        original_register_scanned = getattr(cls, "_vault_register_scanned_projects", None)
        original_register_project = getattr(cls, "_register_project", None)
        original_clone_project = getattr(cls, "_clone_project_from_github", None)
        original_build_projects = cls._build_projects_tab
        original_build_dashboard = getattr(cls, "_build_dashboard", None)
        original_build_settings = getattr(cls, "_build_settings_tab", None)
        original_open_selected = getattr(cls, "_open_selected_project", None)

        def render_quickbar(self: Any) -> None:
            outer_host = getattr(self, "_forge_context_quick_host", None)
            if outer_host is None:
                return
            tk = self.tk
            # Build a complete replacement row first. The old row remains visible
            # until the new row is successfully populated, so rapid navigation can
            # never leave the toolbar empty between destroy/rebuild phases.
            host = tk.Frame(outer_host, bg="#11151a")
            tab = str(getattr(self, "_current_app_tab", "") or "Vault")
            project_page = str(getattr(self, "_forge_current_project_page", "") or "Dashboard")
            vault_view = str(getattr(self, "_forge_vault_view", "") or "Projects")
            context = "Project" if tab == "Project Workspace" else ("Workspace" if tab == "IDE" else tab)

            project_name = str(getattr(getattr(self, "contract", None), "name", "") or Path(self.root_path).name)
            if tab in {"Project Workspace", "IDE"}:
                context_suffix = "PROJECT" if tab == "Project Workspace" else "WORKSPACE"
                label_text = f"{project_name} · {context_suffix}"
                try:
                    from ForgeProjectBranding import project_icon_photo
                    icon_photo, icon_path = project_icon_photo(self, Path(self.root_path), project_name, size=18)
                except Exception:
                    icon_photo, icon_path = None, None
                if icon_photo is not None:
                    self._forge_project_icon_photo = icon_photo
                    self._forge_project_icon_path = str(icon_path or "")
                    icon_label = tk.Label(host, image=icon_photo, bg="#11151a", bd=0, highlightthickness=0)
                    icon_label.pack(side="left", padx=(2, 6))
                else:
                    # Always keep a compact project identity mark even when a project
                    # has not supplied artwork yet. This is deliberately not persisted.
                    initial = (project_name[:1] or "P").upper()
                    icon_label = tk.Label(host, text=initial, width=2, bg="#171c22", fg="#00d9ff",
                                          font=("Segoe UI Semibold", 8), bd=0, highlightthickness=1,
                                          highlightbackground="#28313a")
                    icon_label.pack(side="left", padx=(2, 6), ipady=1)
            else:
                label_text = "VAULT · LIBRARY" if tab == "Vault" and vault_view == "Library" else context.upper()
            label = tk.Label(host, text=label_text, bg="#11151a", fg="#00d9ff", font=("Segoe UI Semibold", 9))
            label.pack(side="left", padx=(0 if tab in {"Project Workspace", "IDE"} else 2, 12))

            def button(text: str, command: Any, *, primary: bool = False) -> None:
                self._button(host, text, command, primary=primary, compact=True).pack(side="left", padx=4)

            def right_button(text: str, command: Any, *, primary: bool = False) -> None:
                self._button(host, text, command, primary=primary, compact=True).pack(side="right", padx=4)

            if tab == "Vault":
                if vault_view == "Library":
                    button("PROJECTS", lambda: _show_vault_projects(self, original_show_app), primary=True)
                    if hasattr(self, "_vault_scan_d_drive"):
                        button("SCAN LIBRARY", self._vault_scan_d_drive)
                    button("REFRESH", self._refresh_clicked)
                else:
                    if hasattr(self, "_register_project"):
                        button("ADD PROJECT", self._register_project, primary=True)
                    if hasattr(self, "_clone_project_from_github"):
                        button("CLONE GITHUB", self._clone_project_from_github)
                    if hasattr(self, "_open_selected_project"):
                        button("OPEN PROJECT", self._open_selected_project)
                    button("AUDIT", lambda: _audit_selected_project(self))
                    button("LIBRARY", lambda: _show_vault_library(self, original_show_app))
                    button("REFRESH", self._refresh_clicked)
            elif tab == "Project Workspace":
                # Project CLI is a distinct project-owned CLI/PCC launch, not the
                # persistent Forge Console. Pack it first on the right so it remains
                # the absolute far-right Project-toolbar action at every width.
                if hasattr(self, "_open_cli"):
                    right_button("PROJECT CLI", self._open_cli)

                if project_page == "Updates":
                    if hasattr(self, "_apply_updates"):
                        button("APPLY UPDATES", self._apply_updates, primary=True)
                    button("REFRESH", self._refresh_clicked)
                elif project_page == "Source Control":
                    button("REFRESH", self._refresh_clicked)
                elif project_page == "Diagnostics":
                    button("DEBUG BUNDLE", lambda: _start_canonical(self, "diagnostics.bundle"), primary=True)
                    button("REFRESH", self._refresh_clicked)
                else:
                    button("FULL GATE", lambda: _start_canonical(self, "gate.full"), primary=True)
                    button("BUILD", lambda: _start_canonical(self, "build.default"))
                    if self.backend and self.backend.supports("test"):
                        button("TEST", lambda: _start_canonical(self, "test.default"))
                    button("RUN", lambda: _start_canonical(self, "run.default"))
                    button("REFRESH", self._refresh_clicked)
            elif tab == "IDE":
                if hasattr(self, "_open_cli"):
                    right_button("PROJECT CLI", self._open_cli)
                button("BUILD", lambda: _start_canonical(self, "build.default"), primary=True)
                button("RUN", lambda: _start_canonical(self, "run.default"))
                button("FULL GATE", lambda: _start_canonical(self, "gate.full"))
                button("REFRESH", self._refresh_clicked)
            else:
                button("REFRESH", self._refresh_clicked)

            old_row = getattr(self, "_forge_quick_row", None)
            host.pack(fill="x", expand=True)
            self._forge_quick_row = host
            if old_row is not None and old_row is not host:
                try:
                    old_row.destroy()
                except Exception:
                    pass

        def build_quick_actions(self: Any, parent: Any) -> None:
            quick = self._panel(parent)
            quick.pack(fill="x", padx=10, pady=(5, 5))
            self._forge_context_quick_host = self.tk.Frame(quick, bg="#11151a")
            self._forge_context_quick_host.pack(fill="x", padx=8, pady=5)
            self._forge_quick_row = None
            self._forge_render_quickbar = lambda: render_quickbar(self)
            render_quickbar(self)

        def normalize_nav(self: Any) -> None:
            _normalize_left_navigation(self)

        def build_projects(self: Any, parent: Any) -> None:
            original_build_projects(self, parent)
            _normalize_vault_projects_content(self, parent)

        def build_dashboard(self: Any, parent: Any) -> None:
            from ForgeProjectDashboard import build
            build(self, parent)

        def build_settings(self: Any, parent: Any) -> None:
            if original_build_settings is not None:
                original_build_settings(self, parent)
            try:
                from ForgeSelfMaintenanceUI import install as install_self_maintenance_ui
                install_self_maintenance_ui(self)
            except Exception:
                pass

        def build_shell(self: Any) -> None:
            original_shell(self)
            normalize_nav(self)
            _normalize_user_facing_terms(self)
            _refresh_visible_identity(self)
            self._forge_vault_view = "Projects"
            self.window.after(60, lambda: _normalize_left_navigation(self))
            self.window.after(80, lambda: render_quickbar(self))
            self.window.after(300, lambda: _prebuild_workspace_shell(self))
            self.window.after(500, lambda: _refresh_visible_identity(self))
            try:
                from ForgeLayoutNormalization import schedule as schedule_layout
                schedule_layout(self, 5)
                self.window.after(120, lambda: schedule_layout(self, 5))
                self.window.after(500, lambda: schedule_layout(self, 5))
                self.window.bind("<Configure>", lambda _e: schedule_layout(self, 90), add="+")
            except Exception:
                pass

        def show_app(self: Any, name: str) -> Any:
            # Startup still asks for the legacy "Projects" surface. Both legacy Projects
            # and the visible Vault button now land on the actionable Vault Projects home.
            if name in {"Projects", "Vault"}:
                _show_vault_projects(self, original_show_app)
                return None
            if name == "Source Control":
                target = "Project Workspace"
            elif name == "Cortex":
                target = "IDE"
            else:
                target = name
            result = original_show_app(self, target)
            self._current_app_tab = target
            _set_top_nav_active(
                self,
                "Project" if target == "Project Workspace"
                else ("Workspace" if target == "IDE" else ("Settings" if target == "Settings" else target)),
            )
            try:
                render_quickbar(self)
                self.window.after(1, lambda target=target: _normalize_surface_once(self, target))
                try:
                    from ForgeLayoutNormalization import schedule as schedule_layout
                    schedule_layout(self, 8)
                except Exception:
                    pass
            except Exception:
                pass
            return result

        def show_page(self: Any, name: str) -> Any:
            self._forge_current_project_page = name
            try:
                from ForgeProjectSurface import ensure_page
                ensure_page(self, name)
            except Exception:
                pass
            result = original_show_page(self, name)
            try:
                render_quickbar(self)
                if name == "Dashboard":
                    try:
                        from ForgeProjectDashboard import refresh as refresh_dashboard
                        self.window.after(20, lambda: refresh_dashboard(self))
                    except Exception:
                        pass
                self.window.after(1, lambda: _normalize_surface_once(self, "Project Workspace"))
                try:
                    from ForgeLayoutNormalization import schedule as schedule_layout
                    schedule_layout(self, 8)
                except Exception:
                    pass
            except Exception:
                pass
            return result

        def activate_project(self: Any, root: Path) -> None:
            original_activate(self, root)
            try:
                from ForgeWorkspaceSurface import invalidate as invalidate_workspace
                invalidate_workspace(self)
            except Exception:
                pass
            try:
                render_quickbar(self)
                _refresh_visible_identity(self)
                from ForgeProjectDashboard import refresh as refresh_dashboard
                self.window.after(80, lambda: refresh_dashboard(self))
            except Exception:
                pass

        def register_scanned_projects(self: Any) -> Any:
            if original_register_scanned is None:
                return None
            result = original_register_scanned(self)
            # Every scanned/registered project receives the standardized ForgePY support
            # handoff and project-side integration handoff automatically.
            try:
                self.window.after(300, lambda: _audit_registered_projects_async(self))
            except Exception:
                _audit_registered_projects_async(self)
            return result

        def register_project(self: Any) -> Any:
            if original_register_project is None:
                return None
            before = {str(entry.registry_id) for entry in self.registry.entries()}
            result = original_register_project(self)
            def audit_new() -> None:
                try:
                    after = list(self.registry.entries())
                    if any(str(entry.registry_id) not in before for entry in after):
                        _audit_registered_projects_async(self)
                except Exception:
                    pass
            try:
                self.window.after(350, audit_new)
            except Exception:
                audit_new()
            return result

        def clone_project(self: Any) -> Any:
            if original_clone_project is None:
                return None
            before = {str(entry.registry_id) for entry in self.registry.entries()}
            result = original_clone_project(self)
            # Clone may complete asynchronously. Check a few times without blocking Tk;
            # stale-aware audit only touches newly missing/outdated handoffs.
            def check(attempts: int = 20) -> None:
                try:
                    after = list(self.registry.entries())
                    if any(str(entry.registry_id) not in before for entry in after):
                        _audit_registered_projects_async(self)
                        return
                except Exception:
                    return
                if attempts > 0:
                    self.window.after(500, lambda: check(attempts - 1))
            try:
                self.window.after(700, check)
            except Exception:
                pass
            return result

        cls._build_global_quick_actions = build_quick_actions
        try:
            from ForgeProjectSurface import build as build_project_surface
            cls._build_workspace_tab = build_project_surface
        except Exception:
            pass
        cls._build_projects_tab = build_projects
        cls._build_dashboard = build_dashboard
        if original_build_settings is not None:
            cls._build_settings_tab = build_settings
        cls._build_shell = build_shell
        cls._show_app_tab = show_app
        cls._show_page = show_page
        cls._activate_project = activate_project
        # Project opening is installed by ForgeProjectInteractionPerformance below.
        # Do not rebind it to a captured legacy synchronous method here.
        if original_register_scanned is not None:
            cls._vault_register_scanned_projects = register_scanned_projects
        if original_register_project is not None:
            cls._register_project = register_project
        if original_clone_project is not None:
            cls._clone_project_from_github = clone_project
        cls._forge_render_context_quickbar = render_quickbar
        cls._forge_audit_registered_projects = _audit_registered_projects_async
        try:
            from ForgeProjectInteractionPerformance import install as install_project_interaction
            cls = install_project_interaction(cls)
        except Exception:
            pass
        try:
            from ForgePerformanceRuntime import install_class as install_performance_runtime
            cls = install_performance_runtime(cls)
        except Exception:
            pass
        try:
            from ForgeNavigationRuntime import install_class as install_navigation_runtime
            cls = install_navigation_runtime(cls)
        except Exception:
            pass
        return cls

    module.install_forge_gui = install_forge_gui


def _focus_console(gui: Any) -> None:
    try:
        panes = gui.global_workspace_panes
        panes.update_idletasks()
        width = max(760, panes.winfo_width())
        panes.sash_place(0, max(420, int(width * 0.70)), 0)
    except Exception:
        pass
    _safe_log(gui, "[INFO] Forge Console is the shared ForgePY execution surface; project CLI remains a separate explicit project action.", "info")


# Compatibility alias for runtime hook naming.
patch_simplified_ux_module = patch_simplified_ux
