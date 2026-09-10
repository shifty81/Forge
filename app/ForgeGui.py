#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence

from PCCSurfaceCommon import (
    BackendClient,
    ProjectContract,
    ProjectRegistry,
    RegisteredProject,
    SurfaceError,
    compact_path,
    latest_debug_bundle,
    open_path,
    resolve_root,
    reveal_file,
    terminate_process_tree,
    validate_surface,
)

from PCCVaultCatalog import (
    baseline_dir as vault_baseline_dir,
    capture_baseline as vault_capture_baseline,
    compare_baseline as vault_compare_baseline,
    catalog_dir as vault_catalog_dir,
    catalog_record as vault_catalog_record,
    classify_path as vault_classify_path,
    latest_summary as vault_latest_summary,
    scan_project as vault_scan_project,
    search_catalog as vault_search_catalog,
    vault_root as global_vault_root,
)
from PCCRepoHygiene import prepare as repo_hygiene_prepare
from ForgeHealth import evaluate_project
from VaultIntake import scan_intake as vault_scan_intake, scan_roots as vault_scan_roots
from VaultPaths import configured_scan_roots, data_root as vault_data_root, downloads_roots, intake_roots, projects_root as vault_projects_root, artifact_central_root, ensure_artifact_project_tree
from VaultPatchEngine import restart_marker_path
from ForgeVersion import VERSION as FORGE_VERSION
from VaultSettings import load_settings, save_settings, set_projects_root, set_section, set_vault_home, set_scan_roots, set_artifact_central_root
from VaultStorage import migrate_home as vault_migrate_home, migrate_project as vault_migrate_project
from VaultDriveIndex import scan as vault_drive_scan, list_projects as vault_drive_projects
from VaultForgejo import server_status as forgejo_server_status
from ForgeSourceControl import status as vault_source_status
from VaultTray import ForgeTray, supported as tray_supported
from VaultIde import list_files as ide_list_files, read_file as ide_read_file, write_file as ide_write_file, runtime_ready as ide_runtime_ready, host_ready as ide_host_ready, launch_monaco as ide_launch_monaco, monaco_root as ide_monaco_root
from VaultCortex import status as cortex_status, start as cortex_start, find_cortex_root
from VaultArtifacts import summary as artifact_summary
from VaultTooling import audit_project as audit_project_tooling, audit_registered_projects as audit_registered_tooling
from VaultBlender import version as blender_version, run_script as blender_run_script
from VaultComponents import inventory as component_inventory
from ForgeProjectSource import clone_repository as forge_clone_repository, project_github as forge_project_github, github_web_url_from_remote
from ForgeUniversalTooling import capability_matrix as forge_capability_matrix, build_all_registered as forge_build_all_registered

GUI_VERSION = f"FORGE-GUI-{FORGE_VERSION}"

BG = "#090b0e"
PANEL = "#11151a"
PANEL_2 = "#171c22"
BORDER = "#28313a"
TEXT = "#edf2f5"
MUTED = "#929aa3"
CYAN = "#00d9ff"
GREEN = "#43f071"
YELLOW = "#ffd44a"
RED = "#ff5d68"


class ForgeGui:
    def __init__(self, root: Path) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog, ttk

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.simpledialog = simpledialog

        self.registry = ProjectRegistry()
        self.root_path = root.resolve()
        self._startup_hygiene: dict[str, Any] = {}
        try:
            self._startup_hygiene = repo_hygiene_prepare(self.root_path, apply=True)
        except Exception as exc:
            self._startup_hygiene = {"moved": 0, "error": str(exc)}
        self.contract = ProjectContract.load(self.root_path)
        self.backend: BackendClient | None = None
        self.backend_error = ""
        self._bind_project_backend()
        self.registry.touch(self.root_path)

        self.window = tk.Tk()
        self.window.title(f"Forge — {self.contract.name}")
        self.window.geometry("1280x860")
        self.window.minsize(1040, 720)
        self.window.configure(bg=BG)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._event_q: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._active_proc: subprocess.Popen[str] | None = None
        self._active_command = ""
        self._last_status: dict[str, Any] = {}
        self._page_frames: dict[str, Any] = {}
        self._page_bodies: dict[str, Any] = {}
        self._status_values: dict[str, Any] = {}
        self._status_leds: dict[str, tuple[Any, Any]] = {}
        self._nav_buttons: dict[str, Any] = {}
        self._app_frames: dict[str, Any] = {}
        self._app_tab_buttons: dict[str, Any] = {}
        self._project_entries_by_id: dict[str, RegisteredProject] = {}
        self._project_health_cache: dict[str, Any] = {}
        self._project_health_generation = 0
        self._active_health_scan_running = False
        self._busy = False
        self._vault_busy = False
        self._vault_cancel = False
        self._vault_node_paths: dict[str, Path] = {}
        self._vault_metrics: dict[str, Any] = {}
        self._intake_stop = threading.Event()
        self._drive_scan_busy = False
        self._project_migration_busy = False
        self._forgejo_status: dict[str, Any] = {}
        self._tray: ForgeTray | None = None
        self._exit_requested = False
        self._app_rail_collapsed = False
        self._health_rail_collapsed = False
        self._ide_paths: dict[str, str] = {}
        self._ide_web = None
        self._settings_pages: dict[str, Any] = {}
        self._settings_nav: dict[str, Any] = {}

        self._configure_styles()
        self._build_shell()
        self._refresh_projects()
        self._show_page("Dashboard")
        self._show_app_tab("Projects")
        self._append_log(f"[PASS] Forge {GUI_VERSION} ACTIVE.\n", "pass")
        self._append_log(f"Active project: {self.contract.name} — {self.root_path}\n", "muted")
        moved = int(self._startup_hygiene.get("moved", 0) or 0)
        if self._startup_hygiene.get("error"):
            self._append_log(f"[WARN] Startup repository hygiene could not complete: {self._startup_hygiene['error']}\n", "warn")
        elif moved:
            self._append_log(f"[PASS] Startup repository hygiene moved {moved} loose operational artifact(s) out of the repository root.\n", "pass")
        else:
            self._append_log("[PASS] Startup repository hygiene: root transport area clean.\n", "pass")
        self._refresh_status_async()
        self.window.after(60, self._drain_events)
        self._start_intake_watcher()
        self._start_tray()
        self._start_configured_services()
        self._schedule_health_refresh()
        self.window.bind("<Unmap>", self._on_window_unmap, add="+")
        if bool((load_settings().get("ui") or {}).get("startMinimized", False)):
            self.window.after(250, self._hide_to_tray)

    # ------------------------------------------------------------------
    # Shell / styling
    # ------------------------------------------------------------------
    def _configure_styles(self) -> None:
        ttk = self.ttk
        style = ttk.Style(self.window)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Treeview",
            background=PANEL_2,
            fieldbackground=PANEL_2,
            foreground=TEXT,
            rowheight=29,
            borderwidth=0,
        )
        style.configure("Treeview.Heading", background=PANEL, foreground=CYAN, relief="flat")
        style.map("Treeview", background=[("selected", "#21404a")], foreground=[("selected", TEXT)])
        style.configure("TProgressbar", troughcolor=PANEL_2, background=CYAN, borderwidth=0)


    def _build_shell(self) -> None:
        tk = self.tk

        header = tk.Frame(self.window, bg=BG, height=82)
        header.pack(fill="x", padx=20, pady=(10, 4))
        header.pack_propagate(False)

        title_block = tk.Frame(header, bg=BG)
        title_block.pack(side="left", fill="y")
        tk.Label(title_block, text="FORGE", bg=BG, fg=CYAN, font=("Segoe UI Semibold", 18)).pack(anchor="w")
        self.active_project_label = tk.Label(title_block, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.active_project_label.pack(anchor="w", pady=(4, 0))
        self._update_header()

        header_actions = tk.Frame(header, bg=BG)
        header_actions.pack(side="right", fill="y")
        tk.Label(header_actions, text=f"v{FORGE_VERSION}  ACTIVE", bg=BG, fg=GREEN, font=("Consolas", 8)).pack(side="left", padx=(0, 9), pady=13)
        self.refresh_btn = self._button(header_actions, "Refresh", self._refresh_clicked, compact=True)
        self.refresh_btn.pack(side="left", padx=3, pady=13)
        self.cli_btn = self._button(header_actions, "Open Project CLI", self._open_cli, compact=True)
        self.cli_btn.pack(side="left", padx=3, pady=13)

        tk.Frame(self.window, bg=CYAN, height=1).pack(fill="x")

        # App-wide navigation is now a collapsible LEFT rail. Projects and Workspace
        # are the first two surfaces instead of consuming another horizontal tab bar.
        self.main_body = tk.Frame(self.window, bg=BG)
        self.main_body.pack(fill="both", expand=True)

        self.app_nav_host = tk.Frame(self.main_body, bg=PANEL, width=158, highlightthickness=1, highlightbackground=BORDER)
        self.app_nav_host.pack(side="left", fill="y")
        self.app_nav_host.pack_propagate(False)
        self.app_nav_header = tk.Frame(self.app_nav_host, bg=PANEL)
        self.app_nav_header.pack(fill="x", padx=8, pady=(8, 6))
        self.app_nav_title = tk.Label(self.app_nav_header, text="FORGE WORKSPACES", bg=PANEL, fg=MUTED, font=("Segoe UI Semibold", 8), anchor="w")
        self.app_nav_title.pack(side="left", fill="x", expand=True)
        self.app_nav_collapse = tk.Button(self.app_nav_header, text="‹", command=self._toggle_app_rail, bg=PANEL, fg=CYAN, activebackground=PANEL_2, activeforeground=CYAN, bd=0, relief="flat", font=("Segoe UI Semibold", 13), cursor="hand2")
        self.app_nav_collapse.pack(side="right")

        nav_items = (("Projects", "Projects"), ("Project Workspace", "Workspace"), ("Vault", "Vault"), ("Forgejo", "Forgejo"), ("IDE", "IDE"), ("Cortex", "Cortex"), ("Settings", "Settings"))
        for name, label in nav_items:
            btn = tk.Button(self.app_nav_host, text=label, command=lambda n=name: self._show_app_tab(n), bg=PANEL, fg=TEXT, activebackground=PANEL_2, activeforeground=CYAN, bd=0, relief="flat", cursor="hand2", font=("Segoe UI Semibold", 10), anchor="w", padx=20, pady=10)
            btn.pack(fill="x", padx=5, pady=1)
            self._app_tab_buttons[name] = btn

        self.app_content = tk.Frame(self.main_body, bg=BG)
        self.app_content.pack(side="left", fill="both", expand=True)
        for name in ("Projects", "Project Workspace", "Vault", "Forgejo", "IDE", "Cortex", "Settings"):
            self._app_frames[name] = tk.Frame(self.app_content, bg=BG)

        self.health_host = tk.Frame(self.main_body, bg=PANEL, width=225, highlightthickness=1, highlightbackground=BORDER)
        self.health_host.pack(side="right", fill="y")
        self.health_host.pack_propagate(False)
        self._build_project_health_gauge(self.health_host)

        self._build_projects_tab(self._app_frames["Projects"])
        self._build_workspace_tab(self._app_frames["Project Workspace"])
        self._build_vault_tab(self._app_frames["Vault"])
        self._build_forgejo_tab(self._app_frames["Forgejo"])
        self._build_ide_tab(self._app_frames["IDE"])
        self._build_cortex_tab(self._app_frames["Cortex"])
        self._build_settings_tab(self._app_frames["Settings"])

        ui = load_settings().get("ui") or {}
        if ui.get("leftRailCollapsed"):
            self.window.after(10, lambda: self._set_app_rail_collapsed(True))
        if ui.get("healthRailCollapsed"):
            self.window.after(10, lambda: self._set_health_rail_collapsed(True))

    def _build_projects_tab(self, parent: Any) -> None:
        tk = self.tk
        ttk = self.ttk

        shell = tk.Frame(parent, bg=BG)
        shell.pack(fill="both", expand=True, padx=20, pady=18)
        self._section_title(
            shell,
            "Registered Projects",
            "Forge project registry. Select a project to load its Project Workspace.",
        )

        toolbar = tk.Frame(shell, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        self._button(toolbar, "Register Local...", self._register_project, primary=True, compact=True).pack(side="left", padx=(0, 6))
        self._button(toolbar, "Clone GitHub...", self._clone_project_from_github, compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Open Workspace", self._open_selected_project, compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Open Folder", self._open_selected_project_folder, compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Open GitHub", self._open_selected_github, compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Remove", self._remove_selected_project, compact=True, danger=True).pack(side="left", padx=6)
        self._button(toolbar, "Rescan", self._refresh_projects, compact=True).pack(side="left", padx=6)

        panel = self._panel(shell)
        panel.pack(fill="both", expand=True)
        self.projects_tree = ttk.Treeview(
            panel,
            columns=("name", "kind", "root", "health", "adapter", "catalog", "last"),
            show="headings",
            selectmode="browse",
        )
        for key, title, width in (
            ("name", "Project", 165),
            ("kind", "Type", 115),
            ("root", "Repository / Root", 375),
            ("health", "Health", 82),
            ("adapter", "Provider", 105),
            ("catalog", "Vault", 95),
            ("last", "Last Opened", 145),
        ):
            self.projects_tree.heading(key, text=title)
            self.projects_tree.column(key, width=width, anchor="w")
        self.projects_tree.tag_configure("ready", foreground=GREEN)
        self.projects_tree.tag_configure("warn", foreground=YELLOW)
        self.projects_tree.tag_configure("adapter", foreground=YELLOW)
        self.projects_tree.tag_configure("missing", foreground=RED)
        scroll = tk.Scrollbar(panel, command=self.projects_tree.yview, bg=PANEL)
        self.projects_tree.configure(yscrollcommand=scroll.set)
        self.projects_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scroll.pack(side="right", fill="y", padx=(0, 8), pady=10)
        self.projects_tree.bind("<<TreeviewSelect>>", self._project_selection_changed)
        self.projects_tree.bind("<Double-1>", lambda _e: self._open_selected_project())

        detail = self._panel(shell, "Selected Project")
        detail.pack(fill="x", pady=(10, 0))
        self.project_detail = tk.Label(
            detail,
            text="Select a registered project.",
            bg=PANEL,
            fg=MUTED,
            justify="left",
            anchor="w",
            font=("Consolas", 9),
        )
        self.project_detail.pack(fill="x", padx=14, pady=(4, 12))


    def _build_workspace_tab(self, parent: Any) -> None:
        tk = self.tk

        # Quick actions span the entire workspace above all three operational panels.
        quick = self._panel(parent)
        quick.pack(fill="x", padx=16, pady=(10, 6))
        quick_row = tk.Frame(quick, bg=PANEL)
        quick_row.pack(fill="x", padx=12, pady=9)
        tk.Label(
            quick_row,
            text="QUICK ACTIONS",
            bg=PANEL,
            fg=CYAN,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left", padx=(2, 14))
        self._button(
            quick_row,
            "FULL GATE / CERTIFY GREEN",
            lambda: self._start_command("full"),
            primary=True,
            compact=True,
        ).pack(side="left", padx=(0, 6))
        self._button(
            quick_row,
            "COMMIT + PUSH GREEN",
            self._commit_push_green,
            compact=True,
        ).pack(side="left", padx=6)
        self._button(
            quick_row,
            "BUILD",
            lambda: self._start_command("build"),
            compact=True,
        ).pack(side="left", padx=6)
        self._button(
            quick_row,
            "RUN",
            lambda: self._start_command("launch-gui"),
            compact=True,
        ).pack(side="left", padx=6)
        self._button(
            quick_row,
            "APPLY UPDATES",
            self._apply_updates,
            compact=True,
        ).pack(side="left", padx=6)
        self._button(
            quick_row,
            "DEBUG BUNDLE",
            lambda: self._start_command("debug-bundle"),
            compact=True,
        ).pack(side="left", padx=6)

        # Main Project Workspace is always three columns:
        #   small operation rail | dynamic command surface | persistent console.
        panes = tk.PanedWindow(
            parent,
            orient="horizontal",
            bg=BG,
            bd=0,
            sashwidth=5,
            sashrelief="flat",
            showhandle=False,
            opaqueresize=True,
        )
        panes.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        self.workspace_panes = panes

        # LEFT: compact navigation authority.
        nav = self._panel(panes)
        nav.configure(width=158)
        nav.pack_propagate(False)
        nav_header = tk.Frame(nav, bg=PANEL)
        nav_header.pack(fill="x", padx=10, pady=(11, 5))
        tk.Label(
            nav_header,
            text="PROJECT OPERATIONS",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI Semibold", 8),
        ).pack(anchor="w")

        nav_pages = (
            ("Dashboard", "Dashboard"),
            ("Build & Run", "Build & Run"),
            ("Updates", "Updates"),
            ("Source Control", "Source Control"),
            ("Diagnostics", "Diagnostics"),
            ("Tooling", "Tooling"),
            ("Advanced Commands", "Advanced Commands"),
        )
        for page, label in nav_pages:
            btn = tk.Button(
                nav,
                text=label,
                anchor="w",
                command=lambda p=page: self._show_page(p),
                bg=PANEL,
                fg=TEXT,
                activebackground=PANEL_2,
                activeforeground=CYAN,
                bd=0,
                relief="flat",
                font=("Segoe UI", 9),
                cursor="hand2",
                padx=12,
                pady=7,
            )
            btn.pack(fill="x", padx=3, pady=1)
            self._nav_buttons[page] = btn

        tk.Frame(nav, bg=BORDER, height=1).pack(fill="x", padx=10, pady=(10, 8))
        self.operation_label = tk.Label(
            nav,
            text="Idle",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
            wraplength=132,
            justify="left",
        )
        self.operation_label.pack(anchor="w", padx=12, pady=(0, 5))
        self.stop_btn = self._button(nav, "Stop Active Job", self._stop_active, compact=True, danger=True)
        # Hidden when idle; it appears only while an operation is actually running.
        self.stop_btn.configure(state="disabled")

        # MIDDLE: clicking the left rail swaps this dynamic command surface.
        center = self._panel(panes)
        self.content = tk.Frame(center, bg=PANEL)
        self.content.pack(fill="both", expand=True, padx=13, pady=12)

        pages = ("Dashboard", "Build & Run", "Updates", "Source Control", "Diagnostics", "Tooling", "Advanced Commands")
        scroll_pages = {"Build & Run", "Updates", "Source Control", "Diagnostics", "Tooling"}
        for page in pages:
            frame = tk.Frame(self.content, bg=PANEL)
            self._page_frames[page] = frame
            self._page_bodies[page] = self._make_scrollable_page(frame) if page in scroll_pages else frame

        self._build_dashboard(self._page_bodies["Dashboard"])
        self._build_build_page(self._page_bodies["Build & Run"])
        self._build_updates_page(self._page_bodies["Updates"])
        self._build_source_page(self._page_bodies["Source Control"])
        self._build_diagnostics_page(self._page_bodies["Diagnostics"])
        self._build_tooling_page(self._page_bodies["Tooling"])
        self._build_commands_page(self._page_bodies["Advanced Commands"])

        # RIGHT: persistent console takes almost half the application by default.
        console = self._panel(panes)
        self.console_panel = console
        console_bar = tk.Frame(console, bg=PANEL)
        console_bar.pack(fill="x", padx=10, pady=(8, 5))
        tk.Label(
            console_bar,
            text="PROJECT CONSOLE",
            bg=PANEL,
            fg=CYAN,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")
        tk.Label(
            console_bar,
            text=GUI_VERSION,
            bg=PANEL,
            fg=MUTED,
            font=("Consolas", 7),
        ).pack(side="left", padx=(7, 0))
        self.console_job_label = tk.Label(
            console_bar,
            text="Idle",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
        )
        self.console_job_label.pack(side="left", padx=(9, 0))
        self._button(console_bar, "Copy All", lambda: self._copy_all(self.console_text), compact=True).pack(side="right", padx=(5, 0))
        self._button(console_bar, "Copy Sel", lambda: self._copy_selection(self.console_text), compact=True).pack(side="right", padx=(5, 0))
        self._button(console_bar, "Clear", self._clear_log, compact=True).pack(side="right", padx=(5, 0))
        self._button(console_bar, "Log", self._open_active_log, compact=True).pack(side="right", padx=(5, 0))

        console_body = tk.Frame(console, bg="#07090b")
        console_body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.console_text = tk.Text(
            console_body,
            bg="#07090b",
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#21404a",
            selectforeground=TEXT,
            bd=0,
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
        )
        cscroll = tk.Scrollbar(console_body, command=self.console_text.yview, bg=PANEL)
        self.console_text.configure(yscrollcommand=cscroll.set)
        self.console_text.pack(side="left", fill="both", expand=True)
        cscroll.pack(side="right", fill="y")
        self._configure_log_tags(self.console_text)

        panes.add(nav, minsize=138, width=158)
        panes.add(center, minsize=330, width=430)
        panes.add(console, minsize=460, width=610)
        self.window.after(160, self._set_workspace_sashes)

        statusbar = tk.Frame(parent, bg="#07090b", height=25, highlightthickness=1, highlightbackground="#20262d")
        statusbar.pack(fill="x", side="bottom")
        statusbar.pack_propagate(False)
        self.footer = tk.Label(
            statusbar,
            text="[Status:Loading]",
            bg="#07090b",
            fg=CYAN,
            font=("Consolas", 8),
            anchor="w",
        )
        self.footer.pack(fill="both", padx=10)

    def _build_vault_tab(self, parent: Any) -> None:
        tk = self.tk
        ttk = self.ttk

        shell = tk.Frame(parent, bg=BG)
        shell.pack(fill="both", expand=True, padx=18, pady=14)
        self._section_title(
            shell,
            "Vault Library",
            "Local-first project intelligence, source/asset catalog, patch intake, build-tool discovery and recovery evidence.",
        )

        toolbar = tk.Frame(shell, bg=BG)
        toolbar.pack(fill="x", pady=(0, 9))
        self._button(toolbar, "Scan Active Project", lambda: self._start_vault_scan(False), primary=True, compact=True).pack(side="left", padx=(0, 6))
        self._button(toolbar, "Deep Hash Scan", lambda: self._start_vault_scan(True), compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Refresh Browser", self._vault_refresh_tree, compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Open Catalog", lambda: open_path(vault_catalog_dir(self.root_path)), compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Open Vault Library", lambda: open_path(global_vault_root()), compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Artifact Central", lambda: open_path(artifact_central_root()), compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Scan Intake", self._vault_scan_intake, compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Capture Baseline", self._vault_capture_baseline, compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Compare Baseline", self._vault_compare_baseline, compact=True).pack(side="left", padx=6)
        self.vault_scan_status = tk.Label(toolbar, text="Idle", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.vault_scan_status.pack(side="right")

        locations = self._panel(shell, "Storage / Portable Locations")
        locations.pack(fill="x", pady=(0, 9))
        loc_body = tk.Frame(locations, bg=PANEL)
        loc_body.pack(fill="x", padx=12, pady=(0, 10))
        loc_text = tk.Frame(loc_body, bg=PANEL)
        loc_text.pack(side="left", fill="x", expand=True)
        self.vault_home_label = tk.Label(loc_text, text="", bg=PANEL, fg=TEXT, font=("Consolas", 8), anchor="w", justify="left")
        self.vault_home_label.pack(fill="x", pady=(0, 2))
        self.vault_projects_label = tk.Label(loc_text, text="", bg=PANEL, fg=MUTED, font=("Consolas", 8), anchor="w", justify="left")
        self.vault_projects_label.pack(fill="x")
        loc_actions = tk.Frame(loc_body, bg=PANEL)
        loc_actions.pack(side="right")
        loc_row1 = tk.Frame(loc_actions, bg=PANEL)
        loc_row1.pack(anchor="e", pady=(0, 4))
        self._button(loc_row1, "Move Vault Home…", self._vault_choose_home, compact=True).pack(side="left", padx=3)
        self._button(loc_row1, "Projects Root…", self._vault_choose_projects_root, compact=True).pack(side="left", padx=3)
        self._button(loc_row1, "Migrate Active Project…", self._vault_migrate_active_project, compact=True).pack(side="left", padx=3)
        loc_row2 = tk.Frame(loc_actions, bg=PANEL)
        loc_row2.pack(anchor="e")
        self._button(loc_row2, "Scan D Drive", self._vault_scan_d_drive, compact=True).pack(side="left", padx=3)
        self._button(loc_row2, "Register Scanned", self._vault_register_scanned_projects, compact=True).pack(side="left", padx=3)
        self._refresh_location_labels()

        metrics = tk.Frame(shell, bg=BG)
        metrics.pack(fill="x", pady=(0, 9))
        self.vault_metric_labels: dict[str, Any] = {}
        for key, title in (
            ("files", "Cataloged"),
            ("source", "Source"),
            ("assets", "Assets"),
            ("commands", "Tool Commands"),
            ("large", "Large Files"),
            ("duplicates", "Duplicates"),
            ("json", "Invalid JSON"),
            ("artifacts", "Artifacts"),
        ):
            card = tk.Frame(metrics, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Label(card, text=title, bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(8, 1))
            value = tk.Label(card, text="—", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12))
            value.pack(anchor="w", padx=12, pady=(0, 8))
            self.vault_metric_labels[key] = value

        panes = tk.PanedWindow(shell, orient="horizontal", bg=BG, sashwidth=5, sashrelief="flat", bd=0)
        panes.pack(fill="both", expand=True)

        left = self._panel(panes, "Project Files")
        right = self._panel(panes, "Catalog Detail")
        panes.add(left, minsize=470, stretch="always")
        panes.add(right, minsize=390, stretch="always")

        search_row = tk.Frame(left, bg=PANEL)
        search_row.pack(fill="x", padx=10, pady=(0, 7))
        self.vault_search_var = tk.StringVar()
        search = tk.Entry(
            search_row,
            textvariable=self.vault_search_var,
            bg="#090c10",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 9),
        )
        search.pack(side="left", fill="x", expand=True, ipady=6)
        search.bind("<Return>", lambda _e: self._vault_search())
        self._button(search_row, "Search Catalog", self._vault_search, compact=True).pack(side="left", padx=(6, 0))
        self._button(search_row, "Clear", self._vault_clear_search, compact=True).pack(side="left", padx=(6, 0))

        tree_shell = tk.Frame(left, bg=PANEL)
        tree_shell.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.vault_tree = ttk.Treeview(
            tree_shell,
            columns=("class", "size", "modified"),
            show="tree headings",
            selectmode="browse",
        )
        self.vault_tree.heading("#0", text="Name")
        self.vault_tree.column("#0", width=360, anchor="w")
        for key, title, width in (("class", "Class", 130), ("size", "Size", 100), ("modified", "Modified", 150)):
            self.vault_tree.heading(key, text=title)
            self.vault_tree.column(key, width=width, anchor="w")
        self.vault_tree.tag_configure("SOURCE", foreground=GREEN)
        self.vault_tree.tag_configure("ASSET", foreground=CYAN)
        self.vault_tree.tag_configure("BUILD_OUTPUT", foreground=MUTED)
        self.vault_tree.tag_configure("DEPENDENCY", foreground=MUTED)
        self.vault_tree.tag_configure("ARCHIVE", foreground=YELLOW)
        self.vault_tree.tag_configure("CONTROL", foreground="#d29dff")
        vscroll = tk.Scrollbar(tree_shell, command=self.vault_tree.yview, bg=PANEL)
        self.vault_tree.configure(yscrollcommand=vscroll.set)
        self.vault_tree.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")
        self.vault_tree.bind("<<TreeviewOpen>>", self._vault_tree_opened)
        self.vault_tree.bind("<<TreeviewSelect>>", self._vault_tree_selected)
        self.vault_tree.bind("<Double-1>", lambda _e: self._vault_open_selected())

        right_actions = tk.Frame(right, bg=PANEL)
        right_actions.pack(fill="x", padx=12, pady=(0, 8))
        self._button(right_actions, "Open", self._vault_open_selected, primary=True, compact=True).pack(side="left", padx=(0, 6))
        self._button(right_actions, "Reveal", self._vault_reveal_selected, compact=True).pack(side="left", padx=6)
        self._button(right_actions, "Copy Path", self._vault_copy_selected_path, compact=True).pack(side="left", padx=6)

        detail_shell = tk.Frame(right, bg="#07090b", highlightthickness=1, highlightbackground=BORDER)
        detail_shell.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.vault_detail = tk.Text(
            detail_shell,
            bg="#07090b",
            fg=TEXT,
            insertbackground=TEXT,
            bd=0,
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
            height=10,
        )
        dscroll = tk.Scrollbar(detail_shell, command=self.vault_detail.yview, bg=PANEL)
        self.vault_detail.configure(yscrollcommand=dscroll.set)
        self.vault_detail.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        dscroll.pack(side="right", fill="y", padx=(4, 8), pady=8)
        self.vault_detail.configure(state="disabled")
        self._vault_refresh_tree()
        self._vault_render_summary(vault_latest_summary(self.root_path))

    def _build_forgejo_tab(self, parent: Any) -> None:
        tk = self.tk
        shell = tk.Frame(parent, bg=BG)
        shell.pack(fill="both", expand=True, padx=20, pady=18)
        self._section_title(
            shell,
            "Local Forgejo",
            "Vault-owned local repository hosting, recovery mirror and source-control authority. GitHub remains a peer remote, not a replacement.",
        )

        status_panel = self._panel(shell, "Instance Status")
        status_panel.pack(fill="x", pady=(0, 10))
        status_body = tk.Frame(status_panel, bg=PANEL)
        status_body.pack(fill="x", padx=12, pady=(0, 10))
        self.forgejo_status_label = tk.Label(
            status_body, text="Loading Forgejo status…", bg=PANEL, fg=MUTED,
            font=("Consolas", 9), anchor="w", justify="left",
        )
        self.forgejo_status_label.pack(side="left", fill="x", expand=True)
        buttons = tk.Frame(status_body, bg=PANEL)
        buttons.pack(side="right")
        self._button(buttons, "Refresh", self._refresh_forgejo_status_async, compact=True).pack(side="left", padx=3)
        self._button(buttons, "Open Web", self._forgejo_open_web, compact=True).pack(side="left", padx=3)
        self._button(buttons, "Open Data", lambda: open_path(Path(str(load_settings().get("forgejo", {}).get("workPath") or vault_data_root() / "Forgejo"))), compact=True).pack(side="left", padx=3)

        self._command_category_list(shell, "Server", (
            ("Start Forgejo", "Start the locally managed Forgejo web server using Vault's configured work path.", lambda: self._start_builtin_forgejo("start"), True),
            ("Stop Forgejo", "Stop the Forgejo process that Vault started and recorded.", lambda: self._start_builtin_forgejo("stop"), False),
            ("Configure Binary", "Point Vault at forgejo.exe without coupling projects to its install location.", self._forgejo_choose_binary, False),
        ))
        self._command_category_list(shell, "Maintenance", (
            ("Doctor (Default)", "Run Forgejo's documented default doctor checks and stream the report into Vault.", lambda: self._start_builtin_forgejo("doctor"), False),
            ("Doctor (All)", "Run all available Forgejo doctor checks without automatically applying fixes.", lambda: self._start_builtin_forgejo("doctor-all"), False),
            ("Backup / Dump", "Create an explicit timestamped Forgejo dump ZIP under Vault's Forgejo backup area.", lambda: self._start_builtin_forgejo("backup"), False),
            ("List Users", "Run the documented Forgejo administrative user-list command against the local instance.", lambda: self._start_builtin_forgejo("users"), False),
        ))
        self._command_category_list(shell, "Actions / Automation", (
            ("Generate Runner Token", "Generate a Forgejo Actions runner-registration token for the local instance.", lambda: self._start_builtin_forgejo("runner-token"), False),
            ("Generate Runner Secret", "Generate a shared secret suitable for idempotent Forgejo Actions runner registration.", lambda: self._start_builtin_forgejo("action-secret"), False),
        ))
        self._command_category_list(shell, "Repositories / API", (
            ("List Repositories", "List repositories visible to Vault's configured Forgejo API token.", lambda: self._start_builtin_forgejo("repos"), True),
            ("Create Repository", "Create a private empty repository through Forgejo's API, then bind it as a Git remote separately.", self._forgejo_create_repo, False),
            ("Bind Active Project", "Configure the active Git working tree with a local Forgejo remote URL.", lambda: self._configure_source_remote("forgejo"), False),
            ("Push Active Project", "Push the active branch to its Forgejo-classified remote without force.", lambda: self._start_builtin_source("push-forgejo"), False),
        ))
        self._refresh_forgejo_status_async()


    def _build_project_health_gauge(self, parent: Any) -> None:
        tk = self.tk
        header = tk.Frame(parent, bg=PANEL)
        header.pack(fill="x", padx=10, pady=(9, 3))
        self.health_title = tk.Label(header, text="FORGE HEALTH", bg=PANEL, fg=MUTED, font=("Segoe UI Semibold", 8), anchor="w")
        self.health_title.pack(side="left", fill="x", expand=True)
        self.health_collapse_btn = tk.Button(header, text="›", command=self._toggle_health_rail, bg=PANEL, fg=CYAN, activebackground=PANEL_2, activeforeground=CYAN, bd=0, relief="flat", font=("Segoe UI Semibold", 13), cursor="hand2")
        self.health_collapse_btn.pack(side="right")

        self.health_expanded = tk.Frame(parent, bg=PANEL)
        self.health_expanded.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.health_canvas = tk.Canvas(self.health_expanded, width=190, height=122, bg=PANEL, highlightthickness=0, bd=0)
        self.health_canvas.pack(anchor="center", pady=(2, 0))
        self.health_canvas.create_arc(18, 22, 172, 176, start=0, extent=180, style="arc", width=12, outline=BORDER, tags=("gauge-bg",))
        self.health_gauge_arc = self.health_canvas.create_arc(18, 22, 172, 176, start=0, extent=0, style="arc", width=12, outline=CYAN)
        self.health_score_text = self.health_canvas.create_text(95, 72, text="—", fill=TEXT, font=("Segoe UI Semibold", 24))
        self.health_level_text = self.health_canvas.create_text(95, 100, text="CHECKING", fill=MUTED, font=("Segoe UI Semibold", 8))
        self.health_project_label = tk.Label(self.health_expanded, text=self.contract.name, bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 10), wraplength=190, justify="center")
        self.health_project_label.pack(fill="x", pady=(0, 7))
        tk.Frame(self.health_expanded, bg=BORDER, height=1).pack(fill="x", padx=4, pady=(0, 6))
        self.health_component_host = tk.Frame(self.health_expanded, bg=PANEL)
        self.health_component_host.pack(fill="x")
        self.health_component_labels: dict[str, tuple[Any, Any]] = {}
        for name in ("Provider", "Git", "GREEN", "Sync", "Updates", "Hygiene", "Tooling"):
            row = tk.Frame(self.health_component_host, bg=PANEL)
            row.pack(fill="x", pady=2)
            left = tk.Label(row, text=name, bg=PANEL, fg=MUTED, font=("Segoe UI", 8), anchor="w")
            left.pack(side="left")
            right = tk.Label(row, text="…", bg=PANEL, fg=MUTED, font=("Segoe UI Semibold", 8), anchor="e")
            right.pack(side="right")
            self.health_component_labels[name] = (left, right)
        self.health_reason_label = tk.Label(self.health_expanded, text="Health evaluation pending.", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=190, justify="left", anchor="nw")
        self.health_reason_label.pack(fill="x", pady=(8, 0))

        self.health_collapsed_btn = tk.Button(parent, text="H\nE\nA\nL\nT\nH", command=self._toggle_health_rail, bg=PANEL, fg=CYAN, activebackground=PANEL_2, activeforeground=CYAN, bd=0, relief="flat", font=("Segoe UI Semibold", 8), cursor="hand2", padx=4)

    def _render_health_gauge(self, health: Any) -> None:
        if not hasattr(self, "health_canvas"):
            return
        score = int(getattr(health, "score", 0) or 0)
        level = str(getattr(health, "level", "UNKNOWN") or "UNKNOWN")
        color = GREEN if level == "GREEN" else (RED if level == "FAIL" else YELLOW)
        try:
            self.health_canvas.itemconfigure(self.health_gauge_arc, extent=max(0, min(180, round(score * 1.8))), outline=color)
            self.health_canvas.itemconfigure(self.health_score_text, text=str(score), fill=color)
            self.health_canvas.itemconfigure(self.health_level_text, text=level, fill=color)
            self.health_project_label.configure(text=self.contract.name)
            components = getattr(health, "components", {}) or {}
            for name, (_, label) in self.health_component_labels.items():
                row = components.get(name) or {}
                state = str(row.get("status") or "—")
                c = GREEN if state == "PASS" else (RED if state == "FAIL" else (YELLOW if state == "WARN" else MUTED))
                label.configure(text=state, fg=c)
            reasons = tuple(getattr(health, "reasons", ()) or ())
            self.health_reason_label.configure(text=(reasons[0] if reasons else "All evaluated authorities are healthy."), fg=(MUTED if not reasons else color))
            if self._tray is not None:
                self._tray.set_status(f"Forge — {self.contract.name} — {level} {score}/100")
        except Exception:
            pass

    def _set_app_rail_collapsed(self, collapsed: bool) -> None:
        self._app_rail_collapsed = bool(collapsed)
        width = 38 if collapsed else 158
        self.app_nav_host.configure(width=width)
        self.app_nav_title.configure(text="" if collapsed else "FORGE WORKSPACES")
        self.app_nav_collapse.configure(text="›" if collapsed else "‹")
        display = {"Projects":"P", "Project Workspace":"W", "Vault":"V", "Forgejo":"F", "IDE":"I", "Cortex":"C", "Settings":"S"}
        for key, btn in self._app_tab_buttons.items():
            btn.configure(text=display.get(key, key[:1]) if collapsed else ("Workspace" if key == "Project Workspace" else key), anchor="center" if collapsed else "w", padx=5 if collapsed else 20)
        try:
            set_section("ui", {"leftRailCollapsed": bool(collapsed)})
        except Exception:
            pass

    def _toggle_app_rail(self) -> None:
        self._set_app_rail_collapsed(not self._app_rail_collapsed)

    def _set_health_rail_collapsed(self, collapsed: bool) -> None:
        self._health_rail_collapsed = bool(collapsed)
        if collapsed:
            self.health_expanded.pack_forget()
            for child in (self.health_title, self.health_collapse_btn):
                try: child.pack_forget()
                except Exception: pass
            try: self.health_host.configure(width=30)
            except Exception: pass
            self.health_collapsed_btn.pack(fill="both", expand=True)
        else:
            self.health_collapsed_btn.pack_forget()
            try: self.health_host.configure(width=225)
            except Exception: pass
            self.health_title.pack(side="left", fill="x", expand=True)
            self.health_collapse_btn.pack(side="right")
            self.health_expanded.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        try:
            set_section("ui", {"healthRailCollapsed": bool(collapsed)})
        except Exception:
            pass

    def _toggle_health_rail(self) -> None:
        self._set_health_rail_collapsed(not self._health_rail_collapsed)

    def _build_ide_tab(self, parent: Any) -> None:
        tk, ttk = self.tk, self.ttk
        shell = tk.Frame(parent, bg=BG)
        shell.pack(fill="both", expand=True, padx=14, pady=12)
        self._section_title(shell, "Forge IDE", "Project-aware source editing. Native editing stays available for recovery; Monaco opens in its own Forge-themed desktop window.")
        toolbar = tk.Frame(shell, bg=BG); toolbar.pack(fill="x", pady=(0, 8))
        self._button(toolbar, "Refresh Files", self._ide_refresh_files, primary=True, compact=True).pack(side="left", padx=(0, 5))
        self._button(toolbar, "Save", self._ide_save_native, compact=True).pack(side="left", padx=5)
        self._button(toolbar, "Install Monaco", self._ide_install_monaco, compact=True).pack(side="left", padx=5)
        self._button(toolbar, "Install IDE Host", self._ide_install_host, compact=True).pack(side="left", padx=5)
        self._button(toolbar, "Open Monaco Window", self._ide_enable_monaco, compact=True).pack(side="left", padx=5)
        self.ide_status_label = tk.Label(toolbar, text="Monaco pop-out ready" if (ide_runtime_ready() and ide_host_ready()) else "Native editor · Monaco/host optional", bg=BG, fg=GREEN if (ide_runtime_ready() and ide_host_ready()) else MUTED, font=("Segoe UI", 8))
        self.ide_status_label.pack(side="right")
        panes=tk.PanedWindow(shell,orient="horizontal",bg=BG,sashwidth=5,bd=0); panes.pack(fill="both",expand=True)
        left=self._panel(panes,"Project Files"); right=self._panel(panes,"Editor"); panes.add(left,minsize=260,width=310); panes.add(right,minsize=560,stretch="always")
        self.ide_tree=ttk.Treeview(left,show="tree",selectmode="browse"); ys=tk.Scrollbar(left,command=self.ide_tree.yview,bg=PANEL); self.ide_tree.configure(yscrollcommand=ys.set); self.ide_tree.pack(side="left",fill="both",expand=True,padx=(8,0),pady=8); ys.pack(side="right",fill="y",padx=(0,6),pady=8)
        self.ide_tree.bind("<<TreeviewSelect>>", self._ide_selection_changed)
        self.ide_editor_host=tk.Frame(right,bg="#07090b"); self.ide_editor_host.pack(fill="both",expand=True,padx=8,pady=8)
        self.ide_editor=tk.Text(self.ide_editor_host,bg="#090b0e",fg=TEXT,insertbackground=CYAN,selectbackground="#21404a",selectforeground=TEXT,bd=0,relief="flat",font=("Consolas",10),undo=True,wrap="none")
        y=tk.Scrollbar(self.ide_editor_host,command=self.ide_editor.yview,bg=PANEL); x=tk.Scrollbar(self.ide_editor_host,command=self.ide_editor.xview,bg=PANEL,orient="horizontal"); self.ide_editor.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        self.ide_editor.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns"); x.grid(row=1,column=0,sticky="ew"); self.ide_editor_host.grid_rowconfigure(0,weight=1); self.ide_editor_host.grid_columnconfigure(0,weight=1)
        self.ide_editor.bind("<Control-s>", lambda _e: (self._ide_save_native(), "break")[1])
        self._ide_refresh_files()

    def _ide_refresh_files(self) -> None:
        if not hasattr(self, "ide_tree"): return
        self.ide_tree.delete(*self.ide_tree.get_children()); self._ide_paths.clear()
        root_id="ide-root"; self.ide_tree.insert("","end",iid=root_id,text=self.contract.name,open=True); self._ide_paths[root_id]=""
        nodes={"":root_id}
        try: files=ide_list_files(self.root_path)
        except Exception as exc:
            self.ide_status_label.configure(text=f"File scan failed: {exc}",fg=RED); return
        for rel in files:
            parts=Path(rel).parts; parent_key=""; parent_iid=root_id
            for part in parts[:-1]:
                key="/".join([x for x in (parent_key,part) if x])
                if key not in nodes:
                    iid=f"d{len(nodes)}"; self.ide_tree.insert(parent_iid,"end",iid=iid,text=part,open=False); nodes[key]=iid; self._ide_paths[iid]=""
                parent_iid=nodes[key]; parent_key=key
            iid=f"f{len(self._ide_paths)}"; self.ide_tree.insert(parent_iid,"end",iid=iid,text=parts[-1]); self._ide_paths[iid]=rel
        self.ide_status_label.configure(text=f"{len(files)} editable files · {'Monaco ready' if ide_runtime_ready() else 'native editor'}",fg=GREEN)

    def _ide_selection_changed(self, _event: Any=None) -> None:
        sel=self.ide_tree.selection()
        if not sel: return
        rel=self._ide_paths.get(sel[0],"")
        if not rel: return
        try: data=ide_read_file(self.root_path,rel)
        except Exception as exc:
            self.ide_status_label.configure(text=str(exc),fg=RED); return
        self._ide_current_path=rel; self.ide_editor.delete("1.0","end"); self.ide_editor.insert("1.0",data["text"]); self.ide_status_label.configure(text=rel,fg=TEXT)

    def _ide_save_native(self) -> None:
        rel=getattr(self,"_ide_current_path","")
        if not rel: return
        try: info=ide_write_file(self.root_path,rel,self.ide_editor.get("1.0","end-1c"))
        except Exception as exc: self._popup("Forge IDE",str(exc),kind="error"); return
        self.ide_status_label.configure(text=f"Saved · {rel} · {info.get('bytes',0)} bytes",fg=GREEN)

    def _ide_install_monaco(self) -> None:
        script=Path(__file__).resolve().parent/"VaultIde.py"
        self._start_builtin_argv([sys.executable,str(script),"install-monaco"],label="ide-install-monaco",cwd=self.root_path,stay_on_tab=True)

    def _ide_install_host(self) -> None:
        script=Path(__file__).resolve().parent/"VaultIde.py"
        self._start_builtin_argv([sys.executable,str(script),"install-host"],label="ide-install-host",cwd=self.root_path,stay_on_tab=True)

    def _ide_enable_monaco(self) -> None:
        if not ide_runtime_ready():
            self._popup("Forge IDE", "Install the local Monaco component first. The native editor remains fully available.", kind="warning")
            return
        if not ide_host_ready():
            self._popup("Forge IDE", "Install the pywebview IDE host first. On Windows it uses WebView2 and runs Monaco in a separate process/window.", kind="warning")
            return
        initial = str(getattr(self, "_ide_current_path", "") or "")
        try:
            ide_launch_monaco(self.root_path, initial_file=initial)
        except Exception as exc:
            self._popup("Forge IDE", f"Monaco pop-out failed. Native editor remains available.\n\n{exc}", kind="error")
            return
        self.ide_status_label.configure(text="Forge Monaco window launched", fg=GREEN)

    def _build_cortex_tab(self, parent: Any) -> None:
        tk=self.tk; shell=tk.Frame(parent,bg=BG); shell.pack(fill="both",expand=True,padx=18,pady=14)
        self._section_title(shell,"Cortex","Cortex remains a standalone application/service, but Vault is its machine/project operations brain and recovery surface.")
        status=self._panel(shell,"Cortex Connection"); status.pack(fill="x",pady=(0,10)); self.cortex_status_label=tk.Label(status,text="Checking…",bg=PANEL,fg=MUTED,font=("Consolas",9),anchor="w",justify="left"); self.cortex_status_label.pack(fill="x",padx=12,pady=(0,10))
        self._command_category_list(shell,"Application / Service",(("Start Cortex","Launch the configured Cortex executable or registered project launcher.",self._cortex_start,True),("Refresh Status","Re-read Cortex registration and service configuration.",self._refresh_cortex_status,False),("Open Cortex Folder","Open the registered Cortex project root.",self._cortex_open_folder,False)))
        self._command_category_list(shell,"Project Authority",(("Open Cortex Workspace","Make Cortex the active Forge project and open its Project Workspace.",self._cortex_open_workspace,True),("Cortex Settings","Open Forge Settings directly to the Cortex integration page.",lambda:(self._show_app_tab("Settings"),self._show_settings_page("Cortex")),False)))
        self._refresh_cortex_status()

    def _refresh_cortex_status(self) -> None:
        if not hasattr(self,"cortex_status_label"): return
        info=cortex_status(); root=info.get("root") or "Not registered"; exe=info.get("executable") or "Auto-discover launcher"; service=info.get("serviceUrl") or "No service URL configured"
        self.cortex_status_label.configure(text=f"Project : {root}\nLaunch  : {exe}\nService : {service}\nVault   : Tool/API integration boundary ready",fg=GREEN if info.get("registered") else YELLOW)

    def _cortex_start(self) -> None:
        try: proc=cortex_start()
        except Exception as exc: self._popup("Cortex",str(exc),kind="error"); return
        if proc is None: self._popup("Cortex","No configured Cortex executable or registered launcher was found. Configure it in Settings > Cortex.",kind="warning")
        else: self._popup("Cortex","Cortex launch requested.",kind="success")

    def _cortex_open_folder(self) -> None:
        root=find_cortex_root(); open_path(root) if root else self._popup("Cortex","Cortex is not registered in Vault.",kind="warning")

    def _cortex_open_workspace(self) -> None:
        root=find_cortex_root()
        if not root: self._popup("Cortex","Cortex is not registered in Vault.",kind="warning"); return
        self._activate_project(root); self._show_app_tab("Project Workspace")

    def _build_settings_tab(self, parent: Any) -> None:
        tk=self.tk; shell=tk.Frame(parent,bg=BG); shell.pack(fill="both",expand=True,padx=14,pady=12)
        self._section_title(shell,"Settings","Vault application, services, storage, intake, source-control, IDE and Cortex integration settings.")
        body=tk.PanedWindow(shell,orient="horizontal",bg=BG,sashwidth=4,bd=0); body.pack(fill="both",expand=True)
        nav=self._panel(body,"SETTINGS"); nav.configure(width=170); nav.pack_propagate(False); pages=tk.Frame(body,bg=BG); body.add(nav,minsize=155,width=170); body.add(pages,minsize=650,stretch="always")
        self._settings_vars={}; self._settings_pages={}; self._settings_nav={}
        for name in ("Services","Storage","Intake & Artifacts","Source Control","IDE","Tooling","Components","Cortex","Security","Interface"):
            btn=tk.Button(nav,text=name,command=lambda n=name:self._show_settings_page(n),bg=PANEL,fg=TEXT,activebackground=PANEL_2,activeforeground=CYAN,bd=0,relief="flat",anchor="w",font=("Segoe UI Semibold",9),padx=14,pady=9,cursor="hand2"); btn.pack(fill="x",padx=5,pady=1); self._settings_nav[name]=btn; self._settings_pages[name]=tk.Frame(pages,bg=BG)
        self._settings_build_pages(); self._show_settings_page("Services")

    def _setting_check(self,parent:Any,key:str,label:str,value:bool,detail:str="") -> None:
        tk=self.tk; var=tk.BooleanVar(value=value); self._settings_vars[key]=var; row=tk.Frame(parent,bg=PANEL); row.pack(fill="x",padx=10,pady=4); cb=tk.Checkbutton(row,text=label,variable=var,bg=PANEL,fg=TEXT,selectcolor="#090b0e",activebackground=PANEL,activeforeground=CYAN,font=("Segoe UI",9),anchor="w"); cb.pack(side="left")
        if detail: tk.Label(row,text=detail,bg=PANEL,fg=MUTED,font=("Segoe UI",8),anchor="w",justify="left",wraplength=470).pack(side="left",padx=(12,0),fill="x",expand=True)

    def _setting_entry(self,parent:Any,key:str,label:str,value:str,detail:str="") -> None:
        tk=self.tk; row=tk.Frame(parent,bg=PANEL); row.pack(fill="x",padx=10,pady=5); tk.Label(row,text=label,bg=PANEL,fg=MUTED,font=("Segoe UI Semibold",8),width=22,anchor="w").pack(side="left"); var=tk.StringVar(value=value); self._settings_vars[key]=var; ent=tk.Entry(row,textvariable=var,bg="#090c10",fg=TEXT,insertbackground=TEXT,relief="flat",font=("Consolas",9)); ent.pack(side="left",fill="x",expand=True,ipady=5)
        if detail: tk.Label(parent,text=detail,bg=PANEL,fg=MUTED,font=("Segoe UI",7),anchor="w",justify="left").pack(fill="x",padx=34,pady=(0,3))

    def _settings_panel(self,page:str,title:str) -> Any:
        panel=self._panel(self._settings_pages[page],title); panel.pack(fill="x",pady=(0,9)); return panel

    def _settings_build_pages(self) -> None:
        cfg=load_settings(); ui=cfg.get("ui") or {}; svc=cfg.get("services") or {}; intake=cfg.get("intake") or {}; sc=cfg.get("sourceControl") or {}; ide=cfg.get("ide") or {}; cx=cfg.get("cortex") or {}; tooling=cfg.get("tooling") or {}; security=cfg.get("security") or {}
        p=self._settings_panel("Services","Background Services")
        self._setting_check(p,"services.intakeWatcher","Downloads / root intake watcher",bool(svc.get("intakeWatcher",True)),"Watches configured intake roots without blocking unrelated project gates.")
        self._setting_check(p,"services.driveWatcher","Drive/project watcher",bool(svc.get("driveWatcher",False)),"Reserved for incremental D: catalog watching; manual scan remains available.")
        self._setting_check(p,"services.forgejoAutoStart","Start Forgejo with Vault",bool(svc.get("forgejoAutoStart",False)),"Starts the Vault-owned local source host when configured.")
        self._setting_check(p,"services.cortexAutoStart","Start Cortex with Vault",bool(svc.get("cortexAutoStart",False)),"Optional; Cortex remains independently launchable.")
        self._command_category_list(self._settings_pages["Services"],"Service Controls",(("Scan Intake Now","Run the intake classifier immediately.",self._vault_scan_intake,True),("Forgejo Status","Open the local source-hosting workspace.",lambda:self._show_app_tab("Forgejo"),False),("Cortex Status","Open Cortex integration status.",lambda:self._show_app_tab("Cortex"),False)))

        p=self._settings_panel("Storage","Portable Storage Authority")
        self._setting_entry(p,"vaultHome","Forge Home",str(cfg.get("vaultHome") or "")); self._setting_entry(p,"projectsRoot","Projects Root",str(cfg.get("projectsRoot") or "")); self._setting_entry(p,"artifactCentralRoot","Artifact Central",str(cfg.get("artifactCentralRoot") or "")); self._setting_entry(p,"scanRoots","Scan Roots",";".join(str(x) for x in cfg.get("scanRoots") or []),"Semicolon-separated roots; D:\\ is supported.")

        p=self._settings_panel("Intake & Artifacts","Package Verification / Classification")
        self._setting_check(p,"intake.watchDownloads","Watch Downloads",bool(intake.get("watchDownloads",True))); self._setting_check(p,"intake.watchProjectRoot","Watch active project/root transport area",bool(intake.get("watchProjectRoot",True))); self._setting_check(p,"intake.requirePackageDate","Require package creation date",bool(intake.get("requirePackageDate",False)),"Legacy packages can remain compatible while new Vault patches are date-stamped."); self._setting_check(p,"intake.archiveNonPatchArtifacts","Archive recognized non-patch artifacts",bool(intake.get("archiveNonPatchArtifacts",True)))
        self._setting_entry(p,"intake.packageClockToleranceHours","ZIP/package clock tolerance (hours)",str(intake.get("packageClockToleranceHours",48))); self._setting_entry(p,"intake.futureClockToleranceMinutes","Future clock tolerance (minutes)",str(intake.get("futureClockToleranceMinutes",10)))
        self._command_category_list(self._settings_pages["Intake & Artifacts"],"Artifact Central",(("Open Artifact Central","Open the durable per-project evidence and artifact hierarchy.",lambda:open_path(artifact_central_root()),True),("Open Active Project Artifacts","Open the selected project's Artifact Central folder.",lambda:open_path(ensure_artifact_project_tree(self.contract.project_id)["root"]),False)))

        p=self._settings_panel("Source Control","Git / Hosted Authorities")
        self._setting_entry(p,"sourceControl.gitBinary","Git binary",str(sc.get("gitBinary") or "")); self._setting_entry(p,"sourceControl.githubCliBinary","GitHub CLI (gh)",str(sc.get("githubCliBinary") or "")); self._setting_entry(p,"sourceControl.defaultGitHubRemote","GitHub remote",str(sc.get("defaultGitHubRemote") or "origin")); self._setting_entry(p,"sourceControl.defaultForgejoRemote","Forgejo remote",str(sc.get("defaultForgejoRemote") or "forgejo")); self._setting_check(p,"sourceControl.fetchOnStatus","Fetch remotes during status",bool(sc.get("fetchOnStatus",False)))

        p=self._settings_panel("IDE","Forge IDE / Monaco Pop-out")
        self._setting_check(p,"ide.enabled","Enable IDE workspace",bool(ide.get("enabled",True))); self._setting_entry(p,"ide.monacoRoot","Monaco component root",str(ide.get("monacoRoot") or "")); self._setting_entry(p,"ide.monacoVersion","Monaco version",str(ide.get("monacoVersion") or "0.56.0")); self._setting_entry(p,"ide.pywebviewVersion","pywebview version",str(ide.get("pywebviewVersion") or "6.2.1")); self._setting_entry(p,"ide.fontSize","Editor font size",str(ide.get("fontSize",13))); self._setting_entry(p,"ide.windowWidth","Pop-out width",str(ide.get("windowWidth",1500))); self._setting_entry(p,"ide.windowHeight","Pop-out height",str(ide.get("windowHeight",920))); self._setting_check(p,"ide.minimap","Monaco minimap",bool(ide.get("minimap",True))); self._command_category_list(self._settings_pages["IDE"],"IDE Runtime",(("Install Monaco","Install the pinned local Monaco package into Forge Home.",self._ide_install_monaco,True),("Install pywebview","Install the BSD-licensed pop-out WebView2 host.",self._ide_install_host,False),("Open Monaco Window","Open the active project in Forge's separate Monaco editor.",self._ide_enable_monaco,False)))

        p=self._settings_panel("Tooling","Project Tool Discovery")
        self._setting_check(p,"tooling.deepScanRegisteredProjects","Deep-scan registered projects",bool(tooling.get("deepScanRegisteredProjects",True)),"Indexes existing project scripts/tools without executing them."); self._setting_check(p,"tooling.includeArchivedTooling","Include archived tooling",bool(tooling.get("includeArchivedTooling",False))); self._setting_entry(p,"tooling.preferredBlenderBinary","Preferred Blender",str(tooling.get("preferredBlenderBinary") or "")); self._command_category_list(self._settings_pages["Tooling"],"Tool Index",(("Audit Active Project","Build a categorized tooling/script report for the active project.",self._tooling_audit,True),("Audit All Registered","Build the global registered-project tool index.",self._tooling_audit_all,False)))

        p=self._settings_panel("Components","Open-source Components")
        inv=component_inventory().get("components",[])
        for row in inv:
            state="READY" if row.get("detected") else "OPTIONAL"
            detail=f"{row.get('name')} · {row.get('license')} · {state} — {row.get('purpose')}"
            self.tk.Label(p,text=detail,bg=PANEL,fg=GREEN if row.get("detected") else MUTED,font=("Segoe UI",8),anchor="w",justify="left").pack(fill="x",padx=10,pady=3)


        p=self._settings_panel("Cortex","Cortex Integration")
        self._setting_entry(p,"cortex.projectRoot","Cortex project root",str(cx.get("projectRoot") or "")); self._setting_entry(p,"cortex.executable","Cortex executable",str(cx.get("executable") or "")); self._setting_entry(p,"cortex.serviceUrl","Cortex service URL",str(cx.get("serviceUrl") or "")); self._setting_entry(p,"cortex.healthPath","Health path",str(cx.get("healthPath") or ""))

        p=self._settings_panel("Security","Verification / Execution Policy")
        self._setting_check(p,"security.strictModernPatches","Strict modern Vault patches",bool(security.get("strictModernPatches",True)),"Modern Vault packages must carry canonical IDs, package time and build binding."); self._setting_entry(p,"security.legacyPatchPolicy","Legacy patch policy",str(security.get("legacyPatchPolicy") or "review"),"Recommended: review. Legacy unbound packages are retained but not auto-applied."); self._setting_check(p,"security.requireModernBuildBinding","Require build binding for modern patches",bool(security.get("requireModernBuildBinding",True))); self._setting_check(p,"security.blenderDisableAutoexec","Disable Blender autoexec for CLI jobs",bool(security.get("blenderDisableAutoexec",True)))

        p=self._settings_panel("Interface","Window / Rails / Tray")
        self._setting_check(p,"ui.closeToTray","Close button hides Vault to tray",bool(ui.get("closeToTray",True))); self._setting_check(p,"ui.minimizeToTray","Minimize hides Vault to tray",bool(ui.get("minimizeToTray",True))); self._setting_check(p,"ui.startMinimized","Start minimized to tray",bool(ui.get("startMinimized",False))); self._setting_check(p,"ui.showTrayNotifications","System tray notifications",bool(ui.get("showTrayNotifications",True))); self._setting_check(p,"ui.leftRailCollapsed","Collapse workspace rail",bool(ui.get("leftRailCollapsed",False))); self._setting_check(p,"ui.healthRailCollapsed","Collapse health rail",bool(ui.get("healthRailCollapsed",False)))
        for name,page in self._settings_pages.items():
            actions=self.tk.Frame(page,bg=BG); actions.pack(fill="x",side="bottom",pady=(8,0)); self._button(actions,"Save Settings",self._settings_save,primary=True,compact=True).pack(side="right")

    def _show_settings_page(self,name:str) -> None:
        for key,frame in self._settings_pages.items(): frame.pack_forget(); self._settings_nav[key].configure(bg=PANEL,fg=TEXT)
        self._settings_pages[name].pack(fill="both",expand=True); self._settings_nav[name].configure(bg=PANEL_2,fg=CYAN)

    def _settings_save(self) -> None:
        data=load_settings()
        def value(key:str): return self._settings_vars[key].get()
        for section in ("ui","services","intake","sourceControl","ide","tooling","cortex","security"):
            out=dict(data.get(section) or {})
            prefix=section+"."
            for key,var in self._settings_vars.items():
                if not key.startswith(prefix): continue
                field=key[len(prefix):]; v=var.get()
                if field in {"packageClockToleranceHours","futureClockToleranceMinutes","fontSize","windowWidth","windowHeight"}:
                    try: v=float(v) if "Tolerance" in field else int(v)
                    except Exception: pass
                out[field]=v
            data[section]=out
        data["vaultHome"]=value("vaultHome"); data["projectsRoot"]=value("projectsRoot"); data["artifactCentralRoot"]=value("artifactCentralRoot"); data["scanRoots"]=[x.strip() for x in str(value("scanRoots")).split(";") if x.strip()]
        try: path=save_settings(data)
        except Exception as exc: self._popup("Vault Settings",str(exc),kind="error"); return
        self._set_app_rail_collapsed(bool(data["ui"].get("leftRailCollapsed"))); self._set_health_rail_collapsed(bool(data["ui"].get("healthRailCollapsed"))); self._refresh_location_labels(); self._popup("Vault Settings",f"Settings saved.\n\n{path}\n\nSome service/component changes take effect after restart.",kind="success")

    @staticmethod
    def _human_bytes(value: int) -> str:
        amount = float(max(0, int(value)))
        units = ["B", "KB", "MB", "GB", "TB"]
        for unit in units:
            if amount < 1024.0 or unit == units[-1]:
                return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
            amount /= 1024.0
        return f"{int(value)} B"

    def _vault_refresh_tree(self) -> None:
        if not hasattr(self, "vault_tree"):
            return
        for iid in self.vault_tree.get_children():
            self.vault_tree.delete(iid)
        self._vault_node_paths.clear()
        root = self.root_path
        iid = "vault-root"
        self.vault_tree.insert("", "end", iid=iid, text=root.name, values=("PRIMARY_PROJECT", "", ""), open=True, tags=("SOURCE",))
        self._vault_node_paths[iid] = root
        self._vault_insert_children(iid, root)
        self._vault_render_summary(vault_latest_summary(root))

    def _vault_insert_children(self, parent_iid: str, path: Path) -> None:
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
        except OSError:
            return
        # Remove lazy placeholder if present.
        for child in self.vault_tree.get_children(parent_iid):
            if str(child).startswith("dummy:"):
                self.vault_tree.delete(child)
        for child in entries:
            try:
                is_dir = child.is_dir()
                stat = child.stat()
            except OSError:
                continue
            classification = vault_classify_path(self.root_path, child, is_dir=is_dir)
            rel = child.relative_to(self.root_path).as_posix()
            iid = "vault:" + rel.replace("/", "\\")
            if self.vault_tree.exists(iid):
                continue
            size = "" if is_dir else self._human_bytes(int(stat.st_size))
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            self.vault_tree.insert(parent_iid, "end", iid=iid, text=child.name, values=(classification, size, modified), tags=(classification,))
            self._vault_node_paths[iid] = child
            if is_dir:
                try:
                    next(child.iterdir())
                    dummy = "dummy:" + iid
                    self.vault_tree.insert(iid, "end", iid=dummy, text="…")
                except (StopIteration, OSError):
                    pass

    def _vault_tree_opened(self, _event: Any = None) -> None:
        iid = self.vault_tree.focus()
        path = self._vault_node_paths.get(iid)
        if path and path.is_dir():
            self._vault_insert_children(iid, path)

    def _vault_tree_selected(self, _event: Any = None) -> None:
        iid = self.vault_tree.focus()
        path = self._vault_node_paths.get(iid)
        if not path:
            return
        self._vault_show_path(path)

    def _vault_show_path(self, path: Path) -> None:
        try:
            rel = path.relative_to(self.root_path).as_posix() if path != self.root_path else "."
        except ValueError:
            rel = str(path)
        try:
            stat = path.stat()
            size = "Directory" if path.is_dir() else self._human_bytes(stat.st_size)
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            size, modified = "Unavailable", "Unavailable"
        classification = "PRIMARY_PROJECT" if path == self.root_path else vault_classify_path(self.root_path, path, is_dir=path.is_dir())
        rec = None if path.is_dir() else vault_catalog_record(self.root_path, rel)
        lines = [
            f"Path           : {path}",
            f"Relative       : {rel}",
            f"Classification : {classification}",
            f"Size           : {size}",
            f"Modified       : {modified}",
        ]
        if rec:
            lines.extend([
                f"Catalog SHA256 : {rec.get('sha256') or '<deferred>'}",
                f"JSON valid     : {rec.get('jsonValid') if rec.get('jsonValid') is not None else 'n/a'}",
                f"Catalog note   : {rec.get('note') or '—'}",
            ])
        else:
            lines.append("Catalog        : Run Scan Active Project to index/hash this item.")
        self.vault_detail.configure(state="normal")
        self.vault_detail.delete("1.0", "end")
        self.vault_detail.insert("1.0", "\n".join(lines))
        self.vault_detail.configure(state="disabled")

    def _vault_selected_path(self) -> Path | None:
        iid = self.vault_tree.focus() if hasattr(self, "vault_tree") else ""
        return self._vault_node_paths.get(iid)

    def _vault_open_selected(self) -> None:
        path = self._vault_selected_path()
        if path:
            open_path(path)

    def _vault_reveal_selected(self) -> None:
        path = self._vault_selected_path()
        if not path:
            return
        if path.is_file():
            reveal_file(path)
        else:
            open_path(path)

    def _vault_copy_selected_path(self) -> None:
        path = self._vault_selected_path()
        if path:
            self._copy_to_clipboard(str(path), "Vault Path")

    def _vault_clear_search(self) -> None:
        if hasattr(self, "vault_search_var"):
            self.vault_search_var.set("")
        self._vault_refresh_tree()

    def _vault_search(self) -> None:
        query = self.vault_search_var.get().strip()
        if not query:
            self._vault_refresh_tree()
            return
        results = vault_search_catalog(self.root_path, query)
        for iid in self.vault_tree.get_children():
            self.vault_tree.delete(iid)
        self._vault_node_paths.clear()
        root_iid = "vault-search"
        self.vault_tree.insert("", "end", iid=root_iid, text=f"Search: {query}", values=("CATALOG_SEARCH", f"{len(results)} result(s)", ""), open=True)
        for index, item in enumerate(results):
            rel = str(item.get("relPath") or "")
            path = self.root_path / Path(rel)
            iid = f"search:{index}"
            self.vault_tree.insert(root_iid, "end", iid=iid, text=rel, values=(item.get("classification") or "", self._human_bytes(int(item.get("bytes") or 0)), ""), tags=(str(item.get("classification") or ""),))
            self._vault_node_paths[iid] = path

    def _start_vault_scan(self, deep: bool) -> None:
        if self._vault_busy:
            self._popup("Vault Scan", "A Vault Library scan is already running.", kind="warning")
            return
        self._vault_busy = True
        self._vault_cancel = False
        self.vault_scan_status.configure(text="Deep hash scan…" if deep else "Scanning…", fg=CYAN)
        root = self.root_path

        def progress(payload: dict[str, Any]) -> None:
            self._event_q.put(("vault-progress", payload))

        def work() -> None:
            try:
                summary = vault_scan_project(root, deep_hash=deep, progress=progress, cancelled=lambda: self._vault_cancel)
                self._event_q.put(("vault-done", (root, summary)))
            except Exception as exc:
                self._event_q.put(("vault-error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _intake_scan_roots(self) -> tuple[Path, ...]:
        cfg = load_settings()
        intake = cfg.get("intake") or {}
        roots: list[Path] = []
        if bool(intake.get("watchDownloads", True)):
            roots.extend(downloads_roots())
        if bool(intake.get("watchProjectRoot", True)):
            roots.append(self.root_path)
            app_root = Path(__file__).resolve().parents[1]
            if app_root.resolve() != self.root_path.resolve():
                roots.append(app_root)
        unique: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            try: key = os.path.normcase(str(root.expanduser().resolve()))
            except Exception: key = os.path.normcase(str(root))
            if key not in seen:
                seen.add(key); unique.append(root)
        return tuple(unique)

    def _trusted_intake_roots(self) -> tuple[Path, ...]:
        roots: list[Path] = []
        intake = (load_settings().get("intake") or {})
        if bool(intake.get("watchProjectRoot", True)):
            roots.append(self.root_path)
            app_root = Path(__file__).resolve().parents[1]
            if app_root.resolve() != self.root_path.resolve():
                roots.append(app_root)
        return tuple(roots)

    def _start_intake_watcher(self) -> None:
        disabled = str(os.environ.get("VAULT_DISABLE_INTAKE_WATCHER") or os.environ.get("FORGE_DISABLE_INTAKE_WATCHER") or "").strip().casefold()
        settings = load_settings()
        enabled = bool((settings.get("services") or {}).get("intakeWatcher", True)) and bool((settings.get("intake") or {}).get("enabled", True))
        if disabled in {"1", "true", "yes", "on"} or not enabled:
            self._append_log("[INFO] Vault intake watcher disabled.\n", "info")
            return

        def work() -> None:
            while not self._intake_stop.wait(3.0):
                try:
                    result = vault_scan_intake(extra_roots=self._trusted_intake_roots(), force_stable=False, remove_source=True)
                except Exception as exc:
                    self._event_q.put(("forge-intake-background-error", str(exc)))
                    continue
                if result.get("ingested") or result.get("artifacts") or result.get("errors"):
                    self._event_q.put(("forge-intake-background", result))

        threading.Thread(target=work, daemon=True, name="VaultIntakeWatcher").start()
        self._append_log("[PASS] Vault intake watcher active: " + ", ".join(str(p) for p in self._intake_scan_roots()) + "\n", "pass")

    def _vault_scan_intake(self) -> None:
        roots = self._intake_scan_roots()
        self._append_log("[INFO] Vault intake scan: " + ", ".join(str(p) for p in roots) + "\n", "info")
        def work() -> None:
            try:
                result = vault_scan_intake(extra_roots=self._trusted_intake_roots(), force_stable=True, remove_source=True)
                self._event_q.put(("forge-intake-done", result))
            except Exception as exc:
                self._event_q.put(("forge-intake-error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _vault_capture_baseline(self) -> None:
        try:
            path = vault_capture_baseline(self.root_path)
        except Exception as exc:
            self._popup("Vault Baseline", str(exc), kind="warning")
            return
        self._append_log(f"[PASS] Vault baseline captured: {path}\n", "pass")
        self._popup("Vault Baseline", f"Baseline captured for {self.contract.name}.\n\n{path}", kind="success")

    def _vault_compare_baseline(self) -> None:
        try:
            result = vault_compare_baseline(self.root_path)
        except Exception as exc:
            self._popup("Vault Baseline", str(exc), kind="warning")
            return
        counts = result.get("counts") or {}
        message = (
            f"Added: {counts.get('added', 0)}\n"
            f"Removed: {counts.get('removed', 0)}\n"
            f"Changed: {counts.get('changed', 0)}\n\n"
            f"Report: {vault_catalog_dir(self.root_path) / 'baseline-comparison.json'}"
        )
        self._append_log(f"[INFO] Vault baseline comparison: {counts}\n", "info")
        self._popup("Vault Baseline Comparison", message, kind="info")

    def _vault_render_summary(self, summary: dict[str, Any] | None) -> None:
        if not hasattr(self, "vault_metric_labels"):
            return
        if not summary:
            for label in self.vault_metric_labels.values():
                label.configure(text="—", fg=MUTED)
            return
        classes = summary.get("classCounts") or {}
        tooling = summary.get("tooling") or {}
        values = {
            "files": int(summary.get("files") or 0),
            "source": int(classes.get("SOURCE") or 0),
            "assets": int(classes.get("ASSET") or 0),
            "commands": int(tooling.get("commandCount") or 0),
            "large": int(summary.get("largeFiles") or 0),
            "duplicates": int(summary.get("duplicateGroups") or 0),
            "json": int(summary.get("invalidJson") or 0),
            "artifacts": int((artifact_summary(self.contract.project_id) or {}).get("files") or 0),
        }
        for key, value in values.items():
            color = RED if key == "json" and value else (YELLOW if key in {"large", "duplicates"} and value else GREEN)
            self.vault_metric_labels[key].configure(text=str(value), fg=color)
        self._vault_metrics = summary

    def _refresh_location_labels(self) -> None:
        if not hasattr(self, "vault_home_label"):
            return
        settings = load_settings()
        home = Path(str(settings.get("vaultHome") or vault_data_root()))
        projects = Path(str(settings.get("projectsRoot") or vault_projects_root()))
        scans = ", ".join(str(p) for p in configured_scan_roots())
        artifacts = Path(str(settings.get("artifactCentralRoot") or artifact_central_root()))
        self.vault_home_label.configure(text=f"Forge Home : {home}   ·   Artifact Central: {artifacts}")
        self.vault_projects_label.configure(text=f"Projects   : {projects}   ·   Scan roots: {scans}")

    def _vault_choose_home(self) -> None:
        current = str(vault_data_root())
        chosen = self.filedialog.askdirectory(title="Choose Forge Home", initialdir=current if Path(current).exists() else None)
        if not chosen:
            return
        source = vault_data_root()
        target = Path(chosen).expanduser().resolve()
        if target.name.casefold() != "vault":
            target = target / "Vault"
        if not self._popup(
            "Migrate Forge Home",
            f"Copy Vault's durable data from:\n{source}\n\nto:\n{target}\n\nThe old location is retained as rollback evidence. Projects are not moved automatically.",
            kind="warning", confirm=True,
        ):
            return
        self.vault_scan_status.configure(text="Migrating Vault home…", fg=CYAN)
        def progress(payload: dict[str, Any]) -> None:
            self._event_q.put(("vault-storage-progress", payload))
        def work() -> None:
            try:
                result = vault_migrate_home(source, target, keep_source=True, progress=progress)
                self._event_q.put(("vault-storage-done", result))
            except Exception as exc:
                self._event_q.put(("vault-storage-error", str(exc)))
        threading.Thread(target=work, daemon=True, name="VaultStorageMigration").start()

    def _vault_choose_projects_root(self) -> None:
        current = vault_projects_root()
        chosen = self.filedialog.askdirectory(title="Choose Default Projects Root", initialdir=str(current) if current.exists() else None)
        if not chosen:
            return
        target = Path(chosen).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        _settings, path = set_projects_root(target)
        self._append_log(f"[PASS] Default projects root set to {target} ({path})\n", "pass")
        self._refresh_location_labels()

    def _vault_migrate_active_project(self) -> None:
        if self._project_migration_busy:
            self._popup("Portable Project", "A project migration is already running.", kind="warning")
            return
        source = self.root_path.resolve()
        target_root = vault_projects_root().resolve()
        try:
            source.relative_to(target_root)
            self._popup("Portable Project", f"This project already lives under the configured Projects Root:\n{source}", kind="success")
            return
        except ValueError:
            pass
        target = target_root / source.name
        if target.exists():
            self._popup("Portable Project", f"Destination already exists:\n{target}\n\nChoose/rename the existing project or change Projects Root first.", kind="warning")
            return
        if not self._popup(
            "Migrate Active Project",
            f"Create a hash-verified portable copy of:\n{source}\n\nunder:\n{target_root}\n\nVault will switch this registry entry to:\n{target}\n\nThe original project is retained as rollback evidence and is NOT deleted.",
            kind="warning", confirm=True,
        ):
            return
        self._project_migration_busy = True
        self.vault_scan_status.configure(text=f"Migrating {source.name} to Projects Root…", fg=CYAN)
        def progress(payload: dict[str, Any]) -> None:
            self._event_q.put(("project-migration-progress", payload))
        def work() -> None:
            try:
                result = vault_migrate_project(source, target_root, keep_source=True, progress=progress)
                self._event_q.put(("project-migration-done", result))
            except Exception as exc:
                self._event_q.put(("project-migration-error", str(exc)))
        threading.Thread(target=work, daemon=True, name="VaultProjectMigration").start()

    def _vault_scan_d_drive(self) -> None:
        if self._drive_scan_busy:
            self._popup("Drive Scan", "A Vault drive/project scan is already running.", kind="warning")
            return
        root = Path("D:/") if os.name == "nt" and Path("D:/").exists() else (configured_scan_roots()[0] if configured_scan_roots() else vault_projects_root())
        self._drive_scan_busy = True
        self.vault_scan_status.configure(text=f"Scanning {root} for projects…", fg=CYAN)
        def progress(payload: dict[str, Any]) -> None:
            self._event_q.put(("drive-scan-progress", payload))
        def work() -> None:
            try:
                result = vault_drive_scan(root, progress=progress)
                self._event_q.put(("drive-scan-done", result))
            except Exception as exc:
                self._event_q.put(("drive-scan-error", str(exc)))
        threading.Thread(target=work, daemon=True, name="VaultDriveScan").start()

    def _vault_register_scanned_projects(self) -> None:
        records = vault_drive_projects()
        if not records:
            self._popup("Register Scanned Projects", "No drive-index projects are available yet. Run Scan D Drive first.", kind="warning")
            return
        added = failed = 0
        for row in records:
            root = Path(str(row.get("root") or ""))
            if not root.is_dir():
                continue
            try:
                self.registry.register(root, make_active=False)
                added += 1
            except Exception:
                failed += 1
        self._refresh_projects()
        self._append_log(f"[PASS] Drive index registered/refreshed {added} project(s); {failed} could not bind.\n", "pass" if not failed else "warn")
        self._popup("Register Scanned Projects", f"Registered/refreshed: {added}\nCould not bind: {failed}", kind="success" if not failed else "warning")

    def _refresh_source_status_async(self) -> None:
        if not hasattr(self, "source_status_label"):
            return
        self.source_status_label.configure(text="Checking Git / GitHub / Forgejo remotes…", fg=MUTED)
        root = self.root_path
        def work() -> None:
            try:
                self._event_q.put(("source-status", vault_source_status(root)))
            except Exception as exc:
                self._event_q.put(("source-status-error", str(exc)))
        threading.Thread(target=work, daemon=True, name="VaultSourceStatus").start()

    def _refresh_forgejo_status_async(self) -> None:
        if not hasattr(self, "forgejo_status_label"):
            return
        self.forgejo_status_label.configure(text="Checking local Forgejo…", fg=MUTED)
        def work() -> None:
            try:
                self._event_q.put(("forgejo-status", forgejo_server_status()))
            except Exception as exc:
                self._event_q.put(("forgejo-status-error", str(exc)))
        threading.Thread(target=work, daemon=True, name="VaultForgejoStatus").start()

    def _forgejo_open_web(self) -> None:
        try:
            from VaultForgejo import open_web
            open_web()
        except Exception as exc:
            self._popup("Forgejo", str(exc), kind="warning")

    def _forgejo_choose_binary(self) -> None:
        chosen = self.filedialog.askopenfilename(title="Select Forgejo Binary", filetypes=[("Forgejo", "forgejo.exe"), ("Executable", "*.exe"), ("All files", "*")])
        if not chosen:
            return
        settings = load_settings()
        forgejo = dict(settings.get("forgejo") or {})
        forgejo["binary"] = str(Path(chosen).resolve())
        settings["forgejo"] = forgejo
        path = save_settings(settings)
        self._append_log(f"[PASS] Forgejo binary configured: {chosen} ({path})\n", "pass")
        self._refresh_forgejo_status_async()

    def _forgejo_create_repo(self) -> None:
        name = self.simpledialog.askstring("Create Forgejo Repository", "Repository name:", parent=self.window)
        if not name or not name.strip():
            return
        self._start_builtin_forgejo("create-repo", ["--name", name.strip()])


    def _make_scrollable_page(self, parent: Any) -> Any:
        """Create a vertically scrollable middle-workspace surface.

        Source Control and Tooling can grow beyond the available center-column height.  Keep
        scrolling local to the command surface so the persistent console and navigation rails
        never move.
        """
        tk = self.tk
        host = tk.Frame(parent, bg=PANEL)
        host.pack(fill="both", expand=True)
        canvas = tk.Canvas(host, bg=PANEL, bd=0, highlightthickness=0)
        scroll = tk.Scrollbar(host, orient="vertical", command=canvas.yview, bg=PANEL)
        body = tk.Frame(canvas, bg=PANEL)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def sync_region(_event: Any = None) -> None:
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass

        def sync_width(event: Any) -> None:
            try:
                canvas.itemconfigure(window_id, width=max(1, int(event.width)))
            except Exception:
                pass

        def wheel(event: Any) -> str:
            delta = int(getattr(event, "delta", 0) or 0)
            if delta:
                canvas.yview_scroll(-1 if delta > 0 else 1, "units")
            return "break"

        body.bind("<Configure>", sync_region, add="+")
        canvas.bind("<Configure>", sync_width, add="+")
        canvas.bind("<MouseWheel>", wheel, add="+")
        body.bind("<MouseWheel>", wheel, add="+")
        return body

    def _panel(self, parent: Any, title: str | None = None) -> Any:
        tk = self.tk
        frame = tk.Frame(parent, bg=BG, bd=0, highlightthickness=0)
        canvas = tk.Canvas(frame, bg=BG, bd=0, highlightthickness=0)
        canvas.place(x=0, y=0, relwidth=1, relheight=1)

        def rounded_rect(c: Any, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: Any) -> int:
            r = max(2, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
            points = [
                x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
                x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
                x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
            ]
            return c.create_polygon(points, smooth=True, splinesteps=18, **kwargs)

        def redraw(_event: Any = None) -> None:
            try:
                w = max(2, frame.winfo_width())
                h = max(2, frame.winfo_height())
                canvas.delete("panel")
                rounded_rect(
                    canvas,
                    1, 1, w - 1, h - 1, 10,
                    fill=PANEL,
                    outline=BORDER,
                    width=1,
                    tags="panel",
                )
            except Exception:
                pass

        frame.bind("<Configure>", redraw, add="+")
        frame._pcc_canvas = canvas  # type: ignore[attr-defined]
        if title:
            tk.Label(
                frame,
                text=title,
                bg=PANEL,
                fg=CYAN,
                font=("Segoe UI Semibold", 10),
            ).pack(anchor="w", padx=13, pady=(11, 5))
        return frame

    def _button(
        self,
        parent: Any,
        text: str,
        command: Callable[[], None],
        *,
        primary: bool = False,
        compact: bool = False,
        danger: bool = False,
    ) -> Any:
        tk = self.tk
        bg = CYAN if primary else (RED if danger else PANEL_2)
        fg = "#001018" if primary else TEXT
        active = "#52e7ff" if primary else ("#ff7a83" if danger else "#24303a")
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("Segoe UI Semibold" if primary else "Segoe UI", 10),
            padx=12 if compact else 18,
            pady=6 if compact else 10,
        )
        button.bind("<Enter>", lambda _e, b=button: b.configure(bg=active))
        button.bind("<Leave>", lambda _e, b=button, c=bg: b.configure(bg=c))
        return button

    def _round_window(self, window: Any) -> None:
        """Best-effort Windows 11 rounded corners for PCC-owned borderless windows."""
        if os.name != "nt":
            return
        try:
            import ctypes
            window.update_idletasks()
            hwnd = int(window.winfo_id())
            parent_hwnd = int(ctypes.windll.user32.GetParent(hwnd))
            target = parent_hwnd or hwnd
            preference = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(target, 33, ctypes.byref(preference), ctypes.sizeof(preference))
        except Exception:
            pass

    def _center_modal(self, dialog: Any, width: int, height: int) -> None:
        dialog.update_idletasks()
        try:
            px = self.window.winfo_rootx()
            py = self.window.winfo_rooty()
            pw = self.window.winfo_width()
            ph = self.window.winfo_height()
            x = px + max(0, (pw - width) // 2)
            y = py + max(0, (ph - height) // 2)
        except Exception:
            sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
            x, y = max(0, (sw - width) // 2), max(0, (sh - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

    def _popup(self, title: str, message: str, *, kind: str = "info", confirm: bool = False, parent: Any | None = None) -> bool:
        tk = self.tk
        host = parent or self.window
        dialog = tk.Toplevel(host)
        dialog.withdraw()
        dialog.configure(bg=BG)
        dialog.overrideredirect(True)
        dialog.transient(host)
        dialog.resizable(False, False)

        accent = RED if kind == "error" else (YELLOW if kind == "warning" else (GREEN if kind == "success" else CYAN))
        outer = tk.Frame(dialog, bg=accent, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        shell = tk.Frame(outer, bg=PANEL)
        shell.pack(fill="both", expand=True)
        tk.Frame(shell, bg=accent, height=4).pack(fill="x")
        tk.Label(shell, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 13), anchor="w").pack(fill="x", padx=18, pady=(16, 6))
        tk.Label(shell, text=message, bg=PANEL, fg=MUTED, font=("Segoe UI", 10), anchor="w", justify="left", wraplength=520).pack(fill="both", expand=True, padx=18, pady=(0, 14))
        result = [False]
        def close(value: bool) -> None:
            result[0] = value
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()
        actions = tk.Frame(shell, bg=PANEL)
        actions.pack(fill="x", padx=16, pady=(0, 16))
        if confirm:
            self._button(actions, "Cancel", lambda: close(False), compact=True).pack(side="right", padx=(8, 0))
            self._button(actions, "Continue", lambda: close(True), primary=True, compact=True).pack(side="right")
        else:
            self._button(actions, "OK", lambda: close(True), primary=True, compact=True).pack(side="right")
        dialog.bind("<Escape>", lambda _e: close(False))
        dialog.bind("<Return>", lambda _e: close(True))
        dialog.protocol("WM_DELETE_WINDOW", lambda: close(False))
        self._center_modal(dialog, 570, 250 if len(message) < 380 else 310)
        self._round_window(dialog)
        dialog.deiconify()
        dialog.lift()
        dialog.grab_set()
        dialog.focus_force()
        host.wait_window(dialog)
        return bool(result[0])


    def _section_title(self, parent: Any, title: str, subtitle: str = "") -> None:
        tk = self.tk
        tk.Label(parent, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 15)).pack(anchor="w")
        if subtitle:
            tk.Label(parent, text=subtitle, bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=520, justify="left").pack(anchor="w", pady=(3, 10))


    def _build_header_health_rail(self, parent: Any) -> None:
        """Compact, separated health monitor shown only in Project Workspace."""
        tk = self.tk

        # Natural-width cluster: no equal-width columns and no full-header stretching.
        rail = tk.Frame(parent, bg=BG)
        rail.pack(anchor="center", pady=(3, 0))
        self.header_health_toolbar = rail

        keys = ("Git", "GREEN", "Updates", "Hygiene", "Provider", "Runtime", "Sync")

        for index, key in enumerate(keys):
            if index:
                separator = tk.Frame(
                    rail,
                    bg="#36404a",
                    width=1,
                    height=31,
                )
                separator.pack(side="left", padx=7, pady=3)
                separator.pack_propagate(False)

            item = tk.Frame(rail, bg=BG)
            item.pack(side="left", padx=1, pady=0)

            # Small muted category label.
            tk.Label(
                item,
                text=key,
                bg=BG,
                fg=MUTED,
                font=("Segoe UI Semibold", 6),
            ).pack(anchor="center", pady=(0, 1))

            # Tiny status lamp + authoritative value.
            value_row = tk.Frame(item, bg=BG)
            value_row.pack(anchor="center")

            led = tk.Canvas(
                value_row,
                width=8,
                height=8,
                bg=BG,
                highlightthickness=0,
                bd=0,
            )
            led.pack(side="left", padx=(0, 3))
            oval = led.create_oval(2, 2, 6, 6, fill=MUTED, outline="")

            value = tk.Label(
                value_row,
                text="Loading",
                bg=BG,
                fg=CYAN,
                font=("Segoe UI Semibold", 7),
            )
            value.pack(side="left")

            self._status_values[key] = value
            self._status_leds[key] = (led, oval)

    def _set_workspace_sashes(self) -> None:
        panes = getattr(self, "workspace_panes", None)
        if panes is None:
            return
        try:
            panes.update_idletasks()
            width = max(900, panes.winfo_width())
            # left ~13%, middle to ~52%, console gets the remaining ~48%.
            panes.sash_place(0, max(145, int(width * 0.13)), 0)
            panes.sash_place(1, max(500, int(width * 0.52)), 0)
        except Exception:
            pass

    def _action_grid(self, parent: Any, actions: Sequence[tuple[str, Callable[[], None], bool]], *, columns: int = 2) -> Any:
        tk = self.tk
        body = tk.Frame(parent, bg=PANEL)
        body.pack(fill="x", padx=4, pady=4)
        for col in range(columns):
            body.grid_columnconfigure(col, weight=1, uniform="actions")
        for index, (label, command, primary) in enumerate(actions):
            row, col = divmod(index, columns)
            btn = self._button(body, label, command, primary=primary, compact=True)
            btn.configure(wraplength=185, justify="center")
            btn.grid(row=row, column=col, sticky="ew", padx=4, pady=4)
        return body


    def _command_category_list(
        self,
        parent: Any,
        title: str,
        items: Sequence[tuple[str, str, Callable[[], None], bool]],
    ) -> Any:
        """Compact vertical command category for the middle workspace column.

        It deliberately mirrors the visual rhythm of the left operation rail: named category,
        separated rows, command at left and a concise purpose statement beside it.
        """
        tk = self.tk
        panel = self._panel(parent, title)
        panel.pack(fill="x", pady=(0, 9))
        body = tk.Frame(panel, bg=PANEL)
        body.pack(fill="x", padx=8, pady=(0, 8))
        for index, (label, description, command, primary) in enumerate(items):
            if index:
                tk.Frame(body, bg=BORDER, height=1).pack(fill="x", padx=2, pady=(3, 3))
            row = tk.Frame(body, bg=PANEL)
            row.pack(fill="x", padx=2, pady=2)
            btn = self._button(row, label, command, primary=primary, compact=True)
            btn.configure(anchor="w", justify="left", width=20)
            btn.pack(side="left", padx=(0, 9), pady=2)
            tk.Label(
                row, text=description, bg=PANEL, fg=MUTED, font=("Segoe UI", 8),
                anchor="w", justify="left", wraplength=215,
            ).pack(side="left", fill="x", expand=True, pady=3)
        return panel


    def _build_health_rail(self, parent: Any) -> None:
        # Legacy compatibility shim. Health is now rendered in the application header.
        return

    def _build_dashboard(self, parent: Any) -> None:
        tk = self.tk
        self._section_title(
            parent,
            "Dashboard",
            "Selected-project authority and the most useful development state at a glance.",
        )
        summary = self._panel(parent, "Current Authority")
        summary.pack(fill="both", expand=True)
        self.summary_text = tk.Text(
            summary,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#21404a",
            selectforeground=TEXT,
            bd=0,
            relief="flat",
            font=("Consolas", 9),
            height=16,
            wrap="word",
        )
        self.summary_text.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.summary_text.configure(state="disabled")


    def _build_build_page(self, parent: Any) -> None:
        self._section_title(parent, "Build & Run", "Build, validate and launch the selected project using discovered or project-native tooling.")
        self._command_category_list(parent, "Build", (
            ("Build Debug", "Build the normal development configuration.", lambda: self._start_command("build"), True),
            ("Build Release", "Build the optimized/release configuration when exposed.", lambda: self._start_command("build-release"), False),
        ))
        self._command_category_list(parent, "Validation", (
            ("Quick Gate", "Fast development validation using the project's available gate.", lambda: self._start_command("quick"), False),
            ("Fast Gate", "Project-defined fast gate or closest discovered validation.", lambda: self._start_command("fast"), False),
            ("Full Gate", "Apply queued root updates first, then certify the full project gate.", lambda: self._start_command("full"), True),
        ))
        self._command_category_list(parent, "Run / Workspace", (
            ("Launch Runtime", "Run the primary game, editor or application target.", lambda: self._start_command("launch-gui"), True),
            ("Open Project Folder", "Open the selected project's physical root.", lambda: open_path(self.root_path), False),
        ))


    def _build_updates_page(self, parent: Any) -> None:
        self._section_title(parent, "Updates", "Downloads are catalog/review only; deliberate root-drop updates use transactional application and recovery evidence.")
        patch_root = lambda: ensure_artifact_project_tree(self.contract.project_id)["patches"]
        review_root = lambda: ensure_artifact_project_tree(self.contract.project_id)["review"]
        self._command_category_list(parent, "Queue", (
            ("Inspect Queue", "Show deliberately queued project updates and validation state.", lambda: self._start_command("patch-status"), True),
            ("Apply Validated Queue", "Stage and apply only deliberately queued updates using the project or Vault transaction engine.", self._apply_updates, False),
            ("Scan Intake", "Catalog Downloads without execution and validate deliberate active-root drops.", self._vault_scan_intake, False),
            ("Available Downloads", "Open downloaded patches that Vault cataloged but will never auto-apply. Approve by deliberately dropping the chosen patch into this project's root.", lambda: open_path(patch_root() / "available"), False),
            ("Refresh Health", "Refresh update, Git and provider health after intake changes.", self._refresh_status_async, False),
        ))
        self._command_category_list(parent, "Evidence / Recovery", (
            ("Review", "Open rejected, legacy, oversized or otherwise non-executable intake evidence.", lambda: open_path(review_root()), False),
            ("Applied", "Open applied patch evidence for this project.", lambda: open_path(patch_root() / "applied"), False),
            ("Failed", "Open failed/rolled-back patch evidence.", lambda: open_path(patch_root() / "failed"), False),
            ("Receipts", "Open transaction receipts and patch lineage.", lambda: open_path(patch_root() / "receipts"), False),
            ("Backups", "Open project-local patch recovery backups.", lambda: open_path(patch_root() / "backups"), False),
        ))


    def _build_source_page(self, parent: Any) -> None:
        self._section_title(parent, "Source Control", "One Git working tree with separate GitHub and local Forgejo authorities.")
        status_panel = self._panel(parent, "Repository Authority")
        status_panel.pack(fill="x", pady=(0, 9))
        body = self.tk.Frame(status_panel, bg=PANEL)
        body.pack(fill="x", padx=10, pady=(0, 9))
        self.source_status_label = self.tk.Label(
            body, text="Git status not loaded yet.", bg=PANEL, fg=MUTED, font=("Consolas", 8), anchor="w", justify="left",
        )
        self.source_status_label.pack(side="left", fill="x", expand=True)
        self._button(body, "Refresh", self._refresh_source_status_async, compact=True).pack(side="right", padx=(8, 0))
        self._command_category_list(parent, "Working Tree", (
            ("Initialize / Adopt Git", "Initialize Git, bind a declared GitHub authority, and safely adopt remote main history without replacing working-tree files.", lambda: self._start_builtin_source("init", ["main", self._active_project_github_hint()]), False),
            ("Status", "Branch, staged/unstaged/untracked files and upstream state.", lambda: self._start_builtin_source("status"), True),
            ("Review Changes", "Show the current diff summary before a gate or commit.", lambda: self._start_builtin_source("review"), False),
            ("Full Diff", "Show the full working-tree diff against HEAD.", lambda: self._start_builtin_source("diff"), False),
            ("Fetch All", "Fetch and prune every configured remote without modifying the working tree.", lambda: self._start_builtin_source("fetch-all"), False),
        ))
        self._command_category_list(parent, "Certified GREEN", (
            ("Commit GREEN", "Commit only through the project's certified GREEN authority.", self._commit_green, True),
            ("Commit + Push GREEN", "Commit certified source, then use the project-protected push path.", self._commit_push_green, False),
        ))
        self._command_category_list(parent, "GitHub", (
            ("Push GitHub", "Push the current branch to every GitHub-classified remote without force.", lambda: self._start_builtin_source("push-github"), False),
            ("Configure Remote", "Add or replace the GitHub remote URL for this working tree.", lambda: self._configure_source_remote("github"), False),
            ("Open GitHub", "Open the active project's GitHub repository in the default web browser.", self._open_active_github, False),
        ))
        self._command_category_list(parent, "Local Forgejo", (
            ("Push Forgejo", "Push the current branch to every local Forgejo remote without force.", lambda: self._start_builtin_source("push-forgejo"), False),
            ("Sync Both", "Push the same current commit to local Forgejo and GitHub remotes.", lambda: self._start_builtin_source("sync-both"), False),
            ("Configure Remote", "Add or replace the local Forgejo remote URL.", lambda: self._configure_source_remote("forgejo"), False),
            ("Open Forgejo", "Open Forge's Forgejo administration surface.", lambda: self._show_app_tab("Forgejo"), False),
        ))
        self._command_category_list(parent, "Branches / History", (
            ("History", "Graph recent commits across local and remote references.", lambda: self._start_builtin_source("history"), False),
            ("Branches", "List local/remote branches and tracking relationships.", lambda: self._start_builtin_source("branches"), False),
            ("Remotes", "List fetch/push URLs and verify GitHub/Forgejo classification.", lambda: self._start_builtin_source("remotes"), False),
            ("Pull FF Only", "Update from the configured upstream without merge commits.", lambda: self._start_builtin_source("pull-ff"), False),
        ))


    def _build_tooling_page(self, parent: Any) -> None:
        tk = self.tk
        self._section_title(parent, "Tooling", "Project-declared and discovered CLI/script tooling, including Blender automation, build systems and validators.")
        self._command_category_list(parent, "Project Tool Inventory", (
            ("Audit Project Tools", "Read declared tool registries and scan active scripts by domain without executing them.", self._tooling_audit, True),
            ("Audit All Projects", "Build Forge's global script/tool index across every registered project, including Blender automation.", self._tooling_audit_all, False),
            ("Capability Matrix", "Show which registered projects expose Build, Gate, Test and Run through native or universal adapters.", self._tooling_capability_matrix, False),
            ("Build All Registered", "Sequentially build every registered project that exposes a build operation; project-native providers stay authoritative.", self._tooling_build_all, False),
            ("Open Tools Folder", "Open the project's existing tools directory; Forge adopts rather than duplicates project tooling.", lambda: open_path(self.root_path / "tools"), False),
            ("Open Tool Report", "Open Artifact Central's generated tooling reports for this project.", lambda: open_path(ensure_artifact_project_tree(self.contract.project_id)["reports"]), False),
        ))
        self._command_category_list(parent, "Blender CLI", (
            ("Blender Version", "Verify the discovered Blender executable through the command-line bridge.", self._tooling_blender_version, True),
            ("Run Blender Script", "Run a selected project Python tool in Blender background mode with blend-file autoexec disabled.", self._tooling_run_blender_script, False),
            ("Open Blender Tools", "Open the project's Blender tooling folder when one exists.", self._tooling_open_blender, False),
        ))
        panel = self._panel(parent, "Inventory Summary")
        panel.pack(fill="both", expand=True)
        self.tooling_text = tk.Text(panel, bg="#07090b", fg=TEXT, insertbackground=TEXT, bd=0, relief="flat", font=("Consolas", 8), wrap="word", height=10)
        self.tooling_text.pack(fill="both", expand=True, padx=9, pady=(0, 9))
        self.tooling_text.insert("1.0", "Run Audit Project Tools to catalog scripts, domains and CLI availability.\n")
        self.tooling_text.configure(state="disabled")

    def _tooling_set_text(self, text: str) -> None:
        if not hasattr(self, "tooling_text"):
            return
        self.tooling_text.configure(state="normal")
        self.tooling_text.delete("1.0", "end")
        self.tooling_text.insert("1.0", text)
        self.tooling_text.configure(state="disabled")

    def _tooling_audit(self) -> None:
        root = self.root_path
        self._tooling_set_text("Auditing project tooling…")
        def work() -> None:
            try:
                result = audit_project_tooling(root)
                self._event_q.put(("tooling-audit-done", (root, result)))
            except Exception as exc:
                self._event_q.put(("tooling-audit-error", (root, str(exc))))
        threading.Thread(target=work, daemon=True, name="VaultToolingAudit").start()


    def _tooling_audit_all(self) -> None:
        self._tooling_set_text("Auditing tooling across all registered projects…")
        def work() -> None:
            try: self._event_q.put(("tooling-all-done", audit_registered_tooling()))
            except Exception as exc: self._event_q.put(("tooling-all-error", str(exc)))
        threading.Thread(target=work, daemon=True, name="VaultGlobalToolingAudit").start()

    def _tooling_capability_matrix(self) -> None:
        try:
            rows = forge_capability_matrix(self.registry)
        except Exception as exc:
            self._popup("Capability Matrix", str(exc), kind="error")
            return
        lines = ["FORGE UNIVERSAL PROJECT CAPABILITY MATRIX", ""]
        for row in rows:
            flags = " ".join(
                f"{name}:{'Y' if row.get(key) else '-'}"
                for name, key in (("Build", "build"), ("Gate", "full"), ("Quick", "quick"), ("Test", "test"), ("Run", "run"))
            )
            lines.append(f"{row.get('name')} [{row.get('kind')}]  {flags}")
            lines.append(f"  Provider: {row.get('provider')}")
            if row.get("toolAuthority"):
                lines.append(f"  Tool authority: {row.get('toolAuthority')}")
            if row.get("error"):
                lines.append(f"  Error: {row.get('error')}")
        self._tooling_set_text("\n".join(lines) + "\n")

    def _tooling_build_all(self) -> None:
        if self._busy:
            self._popup("Build All", "Finish or stop the current Forge job first.", kind="warning")
            return
        if not self._popup(
            "Build All Registered Projects",
            "Forge will sequentially invoke each registered project's strongest available build operation. "
            "Project-native providers and project.control.json commands remain authoritative; projects without "
            "a build capability are skipped.\n\nContinue?",
            kind="warning",
            confirm=True,
        ):
            return
        self._busy = True
        self.operation_label.configure(text="Running: build-all", fg=CYAN)
        self.console_job_label.configure(text="Running: build-all", fg=CYAN)
        self._append_log("\n=== START UNIVERSAL BUILD MATRIX ===\n", "info")

        def emit(text: str) -> None:
            self._event_q.put(("universal-build-log", text))

        def work() -> None:
            try:
                result = forge_build_all_registered(self.registry, emit=emit)
                self._event_q.put(("universal-build-done", result))
            except Exception as exc:
                self._event_q.put(("universal-build-error", str(exc)))

        threading.Thread(target=work, daemon=True, name="ForgeUniversalBuild").start()

    def _tooling_blender_version(self) -> None:
        script = Path(__file__).resolve().parent / "VaultBlender.py"
        self._start_builtin_argv([sys.executable, str(script), "version"], label="blender-version", cwd=self.root_path, stay_on_tab=True)

    def _tooling_run_blender_script(self) -> None:
        path = self.filedialog.askopenfilename(parent=self.window, title="Select Blender Python Script", initialdir=str(self.root_path / "tools" if (self.root_path / "tools").is_dir() else self.root_path), filetypes=[("Python", "*.py"), ("All files", "*.*")])
        if not path:
            return
        selected = Path(path).resolve()
        try:
            selected.relative_to(self.root_path)
        except ValueError:
            self._popup("Blender CLI", "For safety, Vault only executes Blender scripts inside the active project.", kind="warning")
            return
        script = Path(__file__).resolve().parent / "VaultBlender.py"
        self._start_builtin_argv([sys.executable, str(script), "run-script", str(selected)], label="blender-script", cwd=self.root_path, stay_on_tab=True)

    def _tooling_open_blender(self) -> None:
        candidates = [self.root_path / "tools" / "blender", self.root_path / "blender", self.root_path / "tools" / "Blender"]
        target = next((p for p in candidates if p.is_dir()), None)
        if target: open_path(target)
        else: self._popup("Blender Tools", "No Blender tooling directory was discovered in the active project.", kind="warning")

    def _build_diagnostics_page(self, parent: Any) -> None:
        self._section_title(parent, "Diagnostics", "Health, repository hygiene, debug evidence and recovery operations.")
        self._command_category_list(parent, "Project Health", (
            ("Project Self-Test", "Run the project's own control/tooling self-test.", lambda: self._start_command("self-test"), True),
            ("Doctor", "Run the strongest discovered project health diagnostic.", lambda: self._start_command("doctor"), False),
            ("Root Hygiene", "Audit loose operational artifacts and repository-root pollution.", lambda: self._start_command("root-hygiene"), False),
            ("Repair Hygiene", "Apply the project's supported hygiene repair path.", lambda: self._start_command("root-hygiene-fix"), False),
        ))
        self._command_category_list(parent, "Evidence", (
            ("Create Debug Bundle", "Package logs/status/diagnostics for a failed operation.", lambda: self._start_command("debug-bundle"), True),
            ("Verify Latest Debug", "Run the project's latest debug-bundle verification.", lambda: self._start_command("verify-latest-debug"), False),
            ("Open Debug Folder", "Open project debug artifacts.", lambda: open_path(self.root_path / "artifacts" / "debug"), False),
            ("Open Artifacts", "Open the selected project's artifact authority.", lambda: open_path(self.root_path / "artifacts"), False),
        ))


    def _build_logs_page(self, parent: Any) -> None:
        tk = self.tk
        self._section_title(parent, "Logs", "Expanded live view. The same stream remains visible in the Project Console at all times.")
        toolbar = tk.Frame(parent, bg=BG)
        toolbar.pack(fill="x", pady=(0, 8))
        self._button(toolbar, "Copy All", lambda: self._copy_all(self.log_text), primary=True, compact=True).pack(side="left", padx=(0, 6))
        self._button(toolbar, "Copy Selection", lambda: self._copy_selection(self.log_text), compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Clear", self._clear_log, compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Open Active Log", self._open_active_log, compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Open Session Logs", lambda: open_path(self.root_path / "artifacts" / "logs" / "sessions"), compact=True).pack(side="left", padx=6)
        self._button(toolbar, "Open Latest Debug", self._open_latest_debug, compact=True).pack(side="left", padx=6)

        frame = self._panel(parent)
        frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(frame, bg="#07090b", fg=TEXT, insertbackground=TEXT, bd=0, relief="flat", font=("Consolas", 9), wrap="word")
        scroll = tk.Scrollbar(frame, command=self.log_text.yview, bg=PANEL)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scroll.pack(side="right", fill="y", pady=10, padx=(0, 8))
        self._configure_log_tags(self.log_text)


    def _build_commands_page(self, parent: Any) -> None:
        ttk = self.ttk
        self._section_title(
            parent,
            "Advanced Commands",
            "Searchable project/tooling command registry. Normal work should use the curated operation pages.",
        )
        panel = self._panel(parent)
        panel.pack(fill="both", expand=True)
        self.commands_tree = ttk.Treeview(
            panel,
            columns=("key", "label", "risk", "program"),
            show="headings",
        )
        for key, title, width in (
            ("key", "Key", 150),
            ("label", "Label", 230),
            ("risk", "Risk", 80),
            ("program", "Program", 100),
        ):
            self.commands_tree.heading(key, text=title)
            self.commands_tree.column(key, width=width, anchor="w")
        self.commands_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self._reload_registered_commands()

    # ------------------------------------------------------------------
    # App / project navigation
    # ------------------------------------------------------------------

    def _show_app_tab(self, name: str) -> None:
        for key, frame in self._app_frames.items():
            frame.pack_forget()
            btn = self._app_tab_buttons.get(key)
            if btn:
                btn.configure(bg=PANEL, fg=TEXT)
        self._app_frames[name].pack(fill="both", expand=True)
        self._app_tab_buttons[name].configure(bg=PANEL_2, fg=CYAN)

        if name == "Forgejo":
            self._refresh_forgejo_status_async()
        elif name == "Vault":
            self._refresh_location_labels()
        elif name == "IDE":
            self._ide_refresh_files()
        elif name == "Cortex":
            self._refresh_cortex_status()

    def _show_page(self, page: str) -> None:
        for name, frame in self._page_frames.items():
            frame.pack_forget()
            btn = self._nav_buttons.get(name)
            if btn:
                btn.configure(bg=PANEL, fg=TEXT)
        self._page_frames[page].pack(fill="both", expand=True)
        if page in self._nav_buttons:
            self._nav_buttons[page].configure(bg=PANEL_2, fg=CYAN)
        if page == "Source Control":
            self._refresh_source_status_async()

    def _bind_project_backend(self) -> None:
        try:
            self.backend = BackendClient(self.root_path, self.contract)
            self.backend_error = ""
        except SurfaceError as exc:
            self.backend = None
            self.backend_error = str(exc)

    def _activate_project(self, root: Path) -> None:
        if self._busy:
            self._popup("Vault", "Finish or stop the active Forge job before switching projects.", kind="warning")
            return
        target_root = root.resolve()
        activation_hygiene: dict[str, Any] = {}
        try:
            activation_hygiene = repo_hygiene_prepare(target_root, apply=True)
        except Exception as exc:
            activation_hygiene = {"moved": 0, "error": str(exc)}
        try:
            contract = ProjectContract.load(target_root)
        except Exception as exc:
            self._popup("Unable to Load Project", f"{root}\n\n{exc}", kind="error")
            return
        self.root_path = root.resolve()
        self.contract = contract
        self._bind_project_backend()
        self.registry.touch(self.root_path)
        self._last_status = {}
        self._update_header()
        self._reload_registered_commands()
        self._reset_status_cards()
        self._clear_log()
        if hasattr(self, "vault_tree"):
            self._vault_refresh_tree()
            self._vault_render_summary(vault_latest_summary(self.root_path))
        self._append_log(f"Active project changed to {self.contract.name}.\n", "info")
        self._append_log(f"Root: {self.root_path}\n", "muted")
        if activation_hygiene.get("error"):
            self._append_log(f"[WARN] Project activation hygiene: {activation_hygiene['error']}\n", "warn")
        else:
            moved = int(activation_hygiene.get("moved", 0) or 0)
            self._append_log(f"[PASS] Project activation hygiene: {moved} loose operational artifact(s) moved.\n", "pass")
        if self.backend_error:
            self._append_log(f"Vault provider: {self.backend_error}\n", "warn")
            self._render_adapter_unavailable()
        else:
            self._refresh_status_async()
        self._show_page("Dashboard")
        self._show_app_tab("Project Workspace")
        self._refresh_projects()

    def _update_header(self) -> None:
        if not hasattr(self, "active_project_label"):
            return
        if self.backend is None:
            adapter = "Vault scan could not bind operations"
        elif self.backend.provider_mode == "auto-contract":
            adapter = "Vault auto-adapter ready"
        else:
            adapter = "Vault native provider ready"
        self.active_project_label.configure(
            text=f"Active: {self.contract.name}  •  {self.contract.kind}  •  {compact_path(self.root_path, 88)}  •  {adapter}"
        )
        self.window.title(f"Forge — {self.contract.name}")

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------
    def _refresh_projects(self) -> None:
        if not hasattr(self, "projects_tree"):
            return
        self._project_entries_by_id.clear()
        for iid in self.projects_tree.get_children():
            self.projects_tree.delete(iid)
        try:
            # Registration is a live binding, not a one-time label snapshot. Re-scan every
            # existing root so newly standardized project.control.json/root-tool changes are
            # adopted automatically without removing/re-adding the project.
            previous = self.registry.entries()
            for registered in previous:
                if registered.root.is_dir():
                    try:
                        self.registry.register(registered.root, make_active=False)
                    except Exception:
                        pass
            entries = self.registry.entries()
        except Exception as exc:
            self._popup("Project Registry", str(exc), kind="error")
            return
        for entry in entries:
            self._project_entries_by_id[entry.registry_id] = entry
            tag = "ready"
            adapter_text = "Ready"
            health_text = "Checking"
            if not entry.root.is_dir():
                tag, adapter_text, health_text = "missing", "Missing root", "FAIL"
            else:
                try:
                    contract = ProjectContract.load(entry.root)
                    backend = BackendClient(entry.root, contract)
                    adapter_text = "Auto-bound" if backend.provider_mode == "auto-contract" else "Ready"
                    cached_health = self._project_health_cache.get(entry.registry_id)
                    health_text = cached_health.level if cached_health is not None else "Checking"
                    if cached_health is not None and cached_health.level == "FAIL":
                        tag = "missing"
                    elif cached_health is not None and cached_health.level == "WARN":
                        tag = "warn"
                except SurfaceError:
                    tag, adapter_text, health_text = "adapter", "Scan incomplete", "WARN"
                except Exception:
                    tag, adapter_text, health_text = "missing", "Invalid", "FAIL"
            catalog = vault_latest_summary(entry.root) if entry.root.is_dir() else None
            catalog_text = f"{catalog.get('files', 0)} files" if catalog else "Not scanned"
            last = entry.last_opened_utc.replace("T", " ")[:19] if entry.last_opened_utc else "—"
            self.projects_tree.insert(
                "",
                "end",
                iid=entry.registry_id,
                values=(entry.name, entry.kind, str(entry.root), health_text, adapter_text, catalog_text, last),
                tags=(tag,),
            )
        self._refresh_project_health_async(entries)
        current_id = ProjectRegistry._registry_id(self.root_path)
        if current_id in self._project_entries_by_id:
            self.projects_tree.selection_set(current_id)
            self.projects_tree.focus(current_id)
            self._project_selection_changed()

    def _refresh_project_health_async(self, entries: Sequence[RegisteredProject]) -> None:
        self._project_health_generation += 1
        generation = self._project_health_generation
        snapshot = tuple(entries)

        def work() -> None:
            for entry in snapshot:
                if generation != self._project_health_generation:
                    return
                try:
                    contract = ProjectContract.load(entry.root)
                    health = evaluate_project(entry.root, contract)
                except Exception as exc:
                    from VaultHealth import ProjectHealth
                    health = ProjectHealth("FAIL", (str(exc),), {}, "")
                self._event_q.put(("project-health", (generation, entry.registry_id, health)))

        threading.Thread(target=work, daemon=True, name="VaultProjectHealth").start()

    def _selected_project(self) -> RegisteredProject | None:
        sel = self.projects_tree.selection()
        if not sel:
            return None
        return self._project_entries_by_id.get(sel[0])

    def _project_selection_changed(self, _event: Any = None) -> None:
        entry = self._selected_project()
        if entry is None:
            self.project_detail.configure(text="Select a registered project.", fg=MUTED)
            return
        adapter = "Ready"
        detail_color = TEXT
        try:
            contract = ProjectContract.load(entry.root)
            backend = BackendClient(entry.root, contract)
            adapter = "Auto-bound" if backend.provider_mode == "auto-contract" else "Native provider"
            provider = backend.provider_label
            discovery = contract.raw.get("_pccDiscovery") or {}
            source = str(discovery.get("source") or "unknown")
            catalog = vault_latest_summary(entry.root)
            catalog_line = f"{catalog.get('files', 0)} files / {catalog.get('duplicateGroups', 0)} duplicate groups" if catalog else "Not cataloged yet"
            tooling = (catalog or {}).get("tooling") or {}
            capabilities = []
            if tooling.get("buildCapable"): capabilities.append("Build")
            if tooling.get("gateCapable"): capabilities.append("Gate")
            if tooling.get("runCapable"): capabilities.append("Run")
            capability_line = ", ".join(capabilities) if capabilities else f"{len(contract.commands)} discovered command(s)"
            health = self._project_health_cache.get(entry.registry_id)
            health_line = health.label if health is not None else "Checking"
            github_line = str((forge_project_github(entry.root) or {}).get("webUrl") or entry.github_url or "Not configured")
        except Exception as exc:
            adapter = "Scan incomplete"
            provider = str(exc)
            source = "filesystem-scan"
            catalog = vault_latest_summary(entry.root) if entry.root.exists() else None
            catalog_line = f"{catalog.get('files', 0)} files" if catalog else "Not cataloged yet"
            health_line = "WARN — project scan incomplete" if entry.root.exists() else "FAIL — project root missing"
            capability_line = "Scan incomplete"
            github_line = entry.github_url or "Not configured"
            detail_color = YELLOW if entry.root.exists() else RED
        self.project_detail.configure(
            text=(
                f"Project    : {entry.name}\n"
                f"Type       : {entry.kind}\n"
                f"Root       : {entry.root}\n"
                f"Health     : {health_line}\n"
                f"Provider   : {adapter}\n"
                f"Discovery  : {source} (project.control.json optional)\n"
                f"Vault      : {catalog_line}\n"
                f"Capabilities: {capability_line}\n"
                f"GitHub     : {github_line}\n"
                f"Passport   : {self.registry.passport_path(entry.root)}\n"
                f"Provider   : {provider}"
            ),
            fg=detail_color,
        )

    def _clone_project_from_github(self) -> None:
        repo = self.simpledialog.askstring(
            "Clone GitHub Project",
            "GitHub repository URL or owner/repository:\n\nThe project will be cloned into the configured Projects Root.",
            parent=self.window,
        )
        if not repo or not repo.strip():
            return
        projects_root = vault_projects_root()
        self._append_log(f"[INFO] GitHub clone queued: {repo.strip()} -> {projects_root}\n", "info")

        def work() -> None:
            try:
                result = forge_clone_repository(repo.strip(), projects_root=projects_root)
                self._event_q.put(("github-clone-done", result))
            except Exception as exc:
                self._event_q.put(("github-clone-error", str(exc)))

        threading.Thread(target=work, daemon=True, name="ForgeGitHubClone").start()

    def _open_selected_github(self) -> None:
        entry = self._selected_project()
        if entry is None:
            self._popup("Open GitHub", "Select a registered project first.", kind="warning")
            return
        info = forge_project_github(entry.root) if entry.root.is_dir() else {}
        url = str(info.get("webUrl") or "").strip()
        if not url:
            self._popup("Open GitHub", f"No GitHub repository is configured or declared for {entry.name}.", kind="warning")
            return
        webbrowser.open(url, new=2)

    def _open_active_github(self) -> None:
        info = forge_project_github(self.root_path)
        url = str(info.get("webUrl") or "").strip()
        if not url:
            self._popup("Open GitHub", "The active project has no GitHub repository configured or declared.", kind="warning")
            return
        webbrowser.open(url, new=2)

    def _register_project(self) -> None:
        raw = self.filedialog.askdirectory(title="Register Project Root")
        if not raw:
            return
        try:
            entry = self.registry.register(Path(raw), make_active=False)
        except Exception as exc:
            self._popup(
                "Register Project",
                f"Forge could not scan/register this folder.\n\n{exc}",
                kind="error",
            )
            return
        self._refresh_projects()
        if entry.registry_id in self._project_entries_by_id:
            self.projects_tree.selection_set(entry.registry_id)
            self.projects_tree.focus(entry.registry_id)
            self._project_selection_changed()
        self._start_onboarding_scan(entry.root)

    def _start_onboarding_scan(self, root: Path) -> None:
        root = root.resolve()
        self._append_log(f"[INFO] Onboarding scan queued: {root}\n", "info")
        def work() -> None:
            try:
                summary = vault_scan_project(root, deep_hash=False)
                self._event_q.put(("onboard-done", (root, summary)))
            except Exception as exc:
                self._event_q.put(("onboard-error", (root, str(exc))))
        threading.Thread(target=work, daemon=True).start()

    def _remove_selected_project(self) -> None:
        entry = self._selected_project()
        if entry is None:
            return
        if entry.root.resolve() == self.root_path.resolve():
            if not self._popup("Remove Registration", f"Remove the active project '{entry.name}' from the registry? This does not delete any project files.", kind="warning", confirm=True):
                return
        elif not self._popup("Remove Registration", f"Remove '{entry.name}' from the Vault registry? This does not delete any project files.", kind="warning", confirm=True):
            return
        self.registry.remove(entry.registry_id)
        self._refresh_projects()

    def _open_selected_project(self) -> None:
        entry = self._selected_project()
        if entry is None:
            self._popup("Projects", "Select a project first.")
            return
        self._activate_project(entry.root)

    def _open_selected_project_folder(self) -> None:
        entry = self._selected_project()
        if entry:
            open_path(entry.root)

    # ------------------------------------------------------------------
    # Live output / clipboard
    # ------------------------------------------------------------------
    _SEMANTIC_LOG_RE = re.compile(
        r"\b(PASS(?:ED)?|FAIL(?:ED|URE)?|WARN(?:ING)?|ERROR)\b",
        re.IGNORECASE,
    )

    def _configure_log_tags(self, widget: Any) -> None:
        # Console output stays neutral. Only the semantic result token is colored;
        # punctuation/brackets, paths, commands, hashes and surrounding prose remain
        # the normal console foreground.
        widget.tag_configure("semantic-pass", foreground=GREEN)
        widget.tag_configure("semantic-warn", foreground=YELLOW)
        widget.tag_configure("semantic-fail", foreground=RED)

    @staticmethod
    def _semantic_log_tag(token: str) -> str:
        upper = token.upper()
        if upper.startswith("PASS"):
            return "semantic-pass"
        if upper.startswith("WARN"):
            return "semantic-warn"
        return "semantic-fail"

    def _insert_semantic_log(self, widget: Any, text: str) -> None:
        cursor = 0
        for match in self._SEMANTIC_LOG_RE.finditer(text):
            start, end = match.span()
            if start > cursor:
                widget.insert("end", text[cursor:start])
            token = text[start:end]
            widget.insert("end", token, self._semantic_log_tag(token))
            cursor = end
        if cursor < len(text):
            widget.insert("end", text[cursor:])

    def _append_log(self, text: str, tag: str = "") -> None:
        # `tag` is retained for call-site compatibility, but intentionally does not
        # color the entire line. Semantic token coloring is authoritative.
        for widget_name in ("console_text", "log_text"):
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            widget.configure(state="normal")
            self._insert_semantic_log(widget, text)
            widget.see("end")
            widget.configure(state="disabled")

    def _clear_log(self) -> None:
        for widget_name in ("console_text", "log_text"):
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.configure(state="disabled")

    def _copy_to_clipboard(self, text: str, label: str) -> None:
        self.window.clipboard_clear()
        self.window.clipboard_append(text)
        self.window.update_idletasks()
        if hasattr(self, "footer"):
            self.footer.configure(text=f"[Copied:{label}] [{len(text)} chars]", fg=GREEN)

    def _copy_all(self, widget: Any) -> None:
        text = widget.get("1.0", "end-1c")
        if not text:
            self._popup("Copy Console", "There is no console output to copy.")
            return
        self._copy_to_clipboard(text, "All Console Output")

    def _copy_selection(self, widget: Any) -> None:
        try:
            text = widget.get("sel.first", "sel.last")
        except self.tk.TclError:
            self._popup("Copy Selection", "Select console text first, or use Copy All.")
            return
        self._copy_to_clipboard(text, "Console Selection")

    def _open_active_log(self) -> None:
        raw = str(((self._last_status.get("session") or {}).get("log") or "")).strip()
        if raw:
            path = Path(raw)
            if path.exists():
                reveal_file(path)
                return
        open_path(self.root_path / "artifacts" / "logs" / "sessions")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def _refresh_clicked(self) -> None:
        self._refresh_projects()
        self._refresh_status_async()

    def _refresh_status_async(self) -> None:
        if self._busy:
            return
        if self.backend is None:
            self._render_adapter_unavailable()
            return
        self.refresh_btn.configure(state="disabled")
        self.footer.configure(text="[Status:Refreshing]", fg=CYAN)

        def work() -> None:
            try:
                status = self.backend.status() if self.backend is not None else {}
                self._event_q.put(("status", status))
            except Exception as exc:
                self._event_q.put(("status-error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _set_status_card(self, key: str, text: str, color: str) -> None:
        label = self._status_values.get(key)
        if label:
            label.configure(text=text, fg=color)
        led = self._status_leds.get(key)
        if led:
            canvas, oval = led
            # LEDs carry the same authority color as the text. Unknown/loading stays gray/cyan.
            try:
                canvas.itemconfigure(oval, fill=color)
            except Exception:
                pass

    def _reset_status_cards(self) -> None:
        for key in self._status_values:
            self._set_status_card(key, "Loading", CYAN)

    def _render_adapter_unavailable(self) -> None:
        self._set_status_card("Git", "Unknown", MUTED)
        self._set_status_card("GREEN", "Unknown", MUTED)
        self._set_status_card("Updates", "Unknown", MUTED)
        self._set_status_card("Hygiene", "Unknown", MUTED)
        self._set_status_card("Provider", "Needs adapter", YELLOW)
        self._set_status_card("Runtime", "Unknown", MUTED)
        self._set_status_card("Sync", "Unknown", MUTED)
        lines = [
            f"Repository : {self.root_path}",
            f"Project    : {self.contract.name}",
            f"Type       : {self.contract.kind}",
            "Provider   : Needs standardized machine provider",
            f"Detail     : {self.backend_error or 'No provider detected'}",
        ]
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", "\n".join(lines))
        self.summary_text.configure(state="disabled")
        self.footer.configure(text="[Provider:Needs Adapter]", fg=YELLOW)
        self.refresh_btn.configure(state="normal")

    def _render_status(self, status: dict[str, Any]) -> None:
        self._last_status = status
        git = status.get("git") or {}
        patches = status.get("patches") or {}
        hygiene = status.get("hygiene") or {}
        binaries = status.get("binaries") or {}
        tools = status.get("tools") or {}
        source_control = status.get("sourceControl") or {}

        if not git.get("gitReady"):
            git_text, git_color = "Not ready", RED
        elif git.get("clean"):
            git_text, git_color = "Clean", GREEN
        else:
            changed = int(git.get("staged", 0) or 0) + int(git.get("unstaged", 0) or 0) + int(git.get("untracked", 0) or 0)
            git_text, git_color = (f"Modified ({changed})" if changed else "Modified"), YELLOW
        self._set_status_card("Git", git_text, git_color)

        if git.get("greenMatch"):
            green_text, green_color = "MATCH", GREEN
        elif git.get("greenMarker"):
            green_text, green_color = "STALE", YELLOW
        else:
            green_text, green_color = "NONE", MUTED
        self._set_status_card("GREEN", green_text, green_color)

        invalid = int(patches.get("invalid", 0) or 0)
        pending = int(patches.get("pending", 0) or 0)
        if invalid:
            upd_text, upd_color = f"{invalid} invalid", RED
        elif pending:
            upd_text, upd_color = f"{pending} pending", YELLOW
        else:
            upd_text, upd_color = "0 pending", GREEN
        self._set_status_card("Updates", upd_text, upd_color)

        if hygiene.get("clean", True):
            self._set_status_card("Hygiene", "Clean", GREEN)
        else:
            self._set_status_card("Hygiene", f"{hygiene.get('violationCount', '?')} issue(s)", YELLOW)

        self._set_status_card("Provider", "Ready", GREEN)
        runtime_ready = bool(binaries.get("gui"))
        self._set_status_card("Runtime", "Ready" if runtime_ready else "Not built", GREEN if runtime_ready else YELLOW)

        ahead = git.get("ahead")
        behind = git.get("behind")
        if ahead is None or behind is None:
            sync = "Unknown"
            sync_color = MUTED
        elif int(ahead) == 0 and int(behind) == 0:
            sync = "MATCH"
            sync_color = GREEN
        elif int(behind) > 0:
            sync = f"{ahead}↑ {behind}↓"
            sync_color = RED
        else:
            sync = f"{ahead} ahead"
            sync_color = YELLOW
        self._set_status_card("Sync", sync, sync_color)

        provider = self.backend.provider_label if self.backend is not None else "Unavailable"
        toolchain = str(status.get("toolchain") or "").strip()
        if not toolchain:
            ready_tools = [name for name, ready in tools.items() if ready]
            toolchain = ", ".join(ready_tools) if ready_tools else "Not reported"
        lines = [
            f"Repository : {self.root_path}",
            f"Project    : {self.contract.name}",
            f"Branch     : {git.get('branch') or '<none>'} @ {git.get('headShort') or '<unborn>'}",
            f"Git        : {git_text}",
            f"Sync       : {sync}",
            f"GitHub     : {'Configured' if source_control.get('githubConfigured') else 'Needs normalization'}",
            f"Forgejo    : {'Configured' if source_control.get('forgejoConfigured') else 'Needs normalization'}",
            f"GREEN      : {green_text}",
            f"Updates    : {upd_text}",
            f"Hygiene    : {'Clean' if hygiene.get('clean', True) else 'Needs attention'}",
            f"Provider   : {provider}",
            f"Toolchain  : {toolchain}",
            f"Runtime    : {binaries.get('gui') or 'Not built / not reported'}",
            f"Active log : {(status.get('session') or {}).get('log') or '<not reported>'}",
        ]
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", "\n".join(lines))
        self.summary_text.configure(state="disabled")

        self.footer.configure(
            text="[" + "] [".join([f"Git:{git_text}", f"GREEN:{green_text}", f"Updates:{upd_text}", f"Hygiene:{'Clean' if hygiene.get('clean', True) else 'WARN'}"]) + "]",
            fg=CYAN,
        )
        self.refresh_btn.configure(state="normal")

    def _reload_registered_commands(self) -> None:
        if not hasattr(self, "commands_tree"):
            return
        for iid in self.commands_tree.get_children():
            self.commands_tree.delete(iid)
        for item in self.contract.commands:
            self.commands_tree.insert("", "end", values=(item.key, item.label, item.risk, item.program))

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------
    def _start_builtin_argv(self, argv: Sequence[str], *, label: str, cwd: Path | None = None, stay_on_tab: bool = False) -> None:
        """Run a Vault-owned command through the same embedded console/job lifecycle as project providers."""
        if self._busy or (self._active_proc and self._active_proc.poll() is None):
            self._popup("Forge", "Another Forge job is already running.", kind="warning")
            return
        if not stay_on_tab:
            self._show_app_tab("Project Workspace")
        if hasattr(self, "console_text"):
            self.console_text.see("end")
        self._busy = True
        self._active_command = label
        self.operation_label.configure(text=f"Running: {label}", fg=CYAN)
        self.console_job_label.configure(text=f"Running: {label}", fg=CYAN)
        self.stop_btn.configure(state="normal")
        if not self.stop_btn.winfo_ismapped():
            self.stop_btn.pack(fill="x", padx=10, pady=(3, 8))
        self.refresh_btn.configure(state="disabled")
        self._append_log(f"\n=== {datetime.now().strftime('%H:%M:%S')} START {label} ===\n", "info")
        self._append_log("[ProcessHost] Forge-owned embedded command capture ON.\n", "info")
        self.footer.configure(text=f"[Job:Running] [{label}]", fg=CYAN)

        def work() -> None:
            try:
                flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
                proc = subprocess.Popen(
                    list(argv), cwd=str(cwd or self.root_path), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", creationflags=flags,
                )
                self._active_proc = proc
                assert proc.stdout is not None
                for line in proc.stdout:
                    self._event_q.put(("log", line))
                rc = proc.wait()
                self._event_q.put(("done", (label, rc)))
            except Exception as exc:
                self._event_q.put(("command-error", (label, str(exc))))

        threading.Thread(target=work, daemon=True, name=f"ForgeBuiltin-{label}").start()

    def _active_project_github_hint(self) -> str:
        try:
            info = forge_project_github(self.root_path) or {}
            value = str(info.get("cloneUrl") or info.get("webUrl") or "").strip()
            if value:
                return value
        except Exception:
            pass
        target = os.path.normcase(str(self.root_path.resolve()))
        try:
            for entry in self.registry.entries():
                if os.path.normcase(str(entry.root.resolve())) == target and entry.github_url:
                    return str(entry.github_url)
        except Exception:
            pass
        return ""

    def _start_builtin_source(self, action: str, extra: Sequence[str] = ()) -> None:
        script = Path(__file__).resolve().parent / "ForgeSourceControl.py"
        argv = [sys.executable, str(script), action, "--root", str(self.root_path), *[str(x) for x in extra]]
        self._start_builtin_argv(argv, label=f"source-{action}", cwd=self.root_path)

    def _start_builtin_forgejo(self, action: str, extra: Sequence[str] = ()) -> None:
        script = Path(__file__).resolve().parent / "VaultForgejo.py"
        argv = [sys.executable, str(script), action, *[str(x) for x in extra]]
        self._start_builtin_argv(argv, label=f"forgejo-{action}", cwd=Path(str(load_settings().get("forgejo", {}).get("workPath") or vault_data_root() / "Forgejo")), stay_on_tab=True)

    def _configure_source_remote(self, kind: str) -> None:
        kind = kind.casefold()
        if kind not in {"github", "forgejo"}:
            return
        try:
            state = vault_source_status(self.root_path)
        except Exception:
            state = {"remotes": []}
        existing = [x for x in (state.get("remotes") or []) if str(x.get("kind") or "") == kind and str(x.get("direction") or "") == "fetch"]
        default_name = str(existing[0].get("name")) if existing else ("github" if kind == "github" else "forgejo")
        default_url = str(existing[0].get("url")) if existing else ""
        remote_name = self.simpledialog.askstring(
            f"Configure {kind.title()} Remote", "Git remote name:", initialvalue=default_name, parent=self.window,
        )
        if not remote_name or not remote_name.strip():
            return
        url = self.simpledialog.askstring(
            f"Configure {kind.title()} Remote",
            "Remote URL (SSH or HTTPS):", initialvalue=default_url, parent=self.window,
        )
        if not url or not url.strip():
            return
        self._start_builtin_source("set-remote", [remote_name.strip(), url.strip()])

    def _start_command(self, command: str, extra: Sequence[str] = (), *, label: str | None = None) -> None:
        if self.backend is None:
            self._popup("Forge", "Forge could not bind an executable operation provider for this project.", kind="warning")
            return
        if not self.backend.supports(command):
            self._popup(
                "Operation Not Available",
                f"The selected project does not expose an operation mapped to '{command}'.\n\nUse Advanced Commands to review what the project scanner discovered.",
                kind="warning",
            )
            return
        if self._busy or (self._active_proc and self._active_proc.poll() is None):
            self._popup("Forge", "Another Forge job is already running.", kind="warning")
            return
        self._show_app_tab("Project Workspace")
        # The embedded project console is the authoritative visible execution surface.
        # Never require an external console window to understand gate/build/Git progress.
        if hasattr(self, "console_text"):
            self.console_text.see("end")
            self.console_text.focus_set()
        self._busy = True
        self._active_command = label or command
        self.operation_label.configure(text=f"Running: {self._active_command}", fg=CYAN)
        self.console_job_label.configure(text=f"Running: {self._active_command}", fg=CYAN)
        self.stop_btn.configure(state="normal")
        if not self.stop_btn.winfo_ismapped():
            self.stop_btn.pack(fill="x", padx=10, pady=(3, 8))
        self.refresh_btn.configure(state="disabled")
        self._append_log(f"\n=== {datetime.now().strftime('%H:%M:%S')} START {self._active_command} ===\n", "info")
        self._append_log("[ProcessHost] Embedded capture ON / hidden inherited console + universal repo hygiene.\n", "info")
        self.footer.configure(text=f"[Job:Running] [{self._active_command}]", fg=CYAN)

        def work() -> None:
            try:
                backend = self.backend
                if backend is None:
                    raise SurfaceError("Vault project provider became unavailable.")
                proc = backend.popen(command, extra)
                self._active_proc = proc
                assert proc.stdout is not None
                for line in proc.stdout:
                    self._event_q.put(("log", line))
                rc = proc.wait()
                self._event_q.put(("done", (command, rc)))
            except Exception as exc:
                self._event_q.put(("command-error", (command, str(exc))))

        threading.Thread(target=work, daemon=True).start()

    def _stop_active(self) -> None:
        proc = self._active_proc
        if proc and proc.poll() is None:
            self.operation_label.configure(text=f"Stopping: {self._active_command}", fg=YELLOW)
            self.console_job_label.configure(text=f"Stopping: {self._active_command}", fg=YELLOW)
            terminate_process_tree(proc)
            self._append_log("Cancellation requested by operator.\n", "warn")

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self._event_q.get_nowait()
                if kind == "log":
                    line = str(payload)
                    up = line.upper()
                    tag = "fail" if ("FAIL" in up or "ERROR" in up) else ("warn" if "WARN" in up else ("pass" if "PASS" in up or "GREEN" in up else ""))
                    self._append_log(line, tag)
                elif kind == "done":
                    command, rc = payload
                    self._active_proc = None
                    self._busy = False
                    self.stop_btn.configure(state="disabled")
                    self.stop_btn.pack_forget()
                    color = GREEN if rc == 0 else RED
                    state = "PASS" if rc == 0 else f"FAIL ({rc})"
                    self.operation_label.configure(text=f"Last: {command} {state}", fg=color)
                    self.console_job_label.configure(text=f"Last: {command} {state}", fg=color)
                    self._append_log(f"=== END {command}: {state} ===\n", "pass" if rc == 0 else "fail")
                    self.footer.configure(text=f"[Last:{command}] [{state}]", fg=color)
                    self._refresh_status_async()
                    if str(command).startswith("forgejo-"):
                        self._refresh_forgejo_status_async()
                    if str(command).startswith("source-"):
                        self._refresh_projects()
                        self._refresh_source_status_async()
                    if rc == 0:
                        self._offer_restart_if_updated()
                elif kind == "command-error":
                    command, detail = payload
                    self._active_proc = None
                    self._busy = False
                    self.stop_btn.configure(state="disabled")
                    self.stop_btn.pack_forget()
                    self.operation_label.configure(text=f"Last: {command} FAIL", fg=RED)
                    self.console_job_label.configure(text=f"Last: {command} FAIL", fg=RED)
                    self._append_log(f"ERROR: {detail}\n", "fail")
                    self._popup("Vault Command Failed", detail, kind="error")
                    self._refresh_status_async()
                elif kind == "github-clone-done":
                    result = payload or {}
                    root = Path(str(result.get("root") or ""))
                    try:
                        entry = self.registry.register(root, make_active=False)
                    except Exception as exc:
                        self._append_log(f"[FAIL] GitHub clone completed but project registration failed: {exc}\n", "fail")
                        self._popup("GitHub Clone", f"Clone completed at:\n{root}\n\nRegistration failed: {exc}", kind="error")
                    else:
                        state = "reused" if result.get("alreadyPresent") else "cloned"
                        self._append_log(f"[PASS] GitHub project {state}: {result.get('webUrl')} -> {root}\n", "pass")
                        self._refresh_projects()
                        if entry.registry_id in self._project_entries_by_id:
                            self.projects_tree.selection_set(entry.registry_id)
                            self.projects_tree.focus(entry.registry_id)
                            self._project_selection_changed()
                        self._start_onboarding_scan(root)
                        self._popup("GitHub Project Ready", f"{entry.name}\n{root}\n\n{result.get('webUrl')}", kind="success")
                elif kind == "github-clone-error":
                    self._append_log(f"[FAIL] GitHub clone: {payload}\n", "fail")
                    self._popup("GitHub Clone Failed", str(payload), kind="error")
                elif kind == "onboard-done":
                    root, summary = payload
                    self._append_log(f"[PASS] Project onboarding catalog complete: {root} ({summary.get('files', 0)} files)\n", "pass")
                    self._refresh_projects()
                    if Path(root).resolve() == self.root_path.resolve():
                        self._vault_render_summary(summary)
                elif kind == "project-health":
                    generation, registry_id, health = payload
                    if generation == self._project_health_generation and registry_id in self._project_entries_by_id:
                        self._project_health_cache[registry_id] = health
                        if self.projects_tree.exists(registry_id):
                            values = list(self.projects_tree.item(registry_id, "values"))
                            if len(values) >= 4:
                                values[3] = health.level
                                tag = "missing" if health.level == "FAIL" else ("warn" if health.level == "WARN" else "ready")
                                self.projects_tree.item(registry_id, values=values, tags=(tag,))
                        selected = self._selected_project()
                        if selected is not None and selected.registry_id == registry_id:
                            self._project_selection_changed()
                        entry = self._project_entries_by_id.get(registry_id)
                        if entry is not None and entry.root.resolve() == self.root_path.resolve():
                            self._render_health_gauge(health)
                elif kind == "active-health":
                    root, health = payload
                    if Path(root).resolve() == self.root_path.resolve():
                        self._render_health_gauge(health)
                elif kind == "active-health-idle":
                    self._active_health_scan_running = False
                elif kind == "active-health-error":
                    root, detail = payload
                    if Path(root).resolve() == self.root_path.resolve():
                        self._append_log(f"[WARN] Active health refresh: {detail}\n", "warn")
                elif kind == "tray-command":
                    self._handle_tray_command(str(payload))
                elif kind == "ide-web-failed":
                    self._ide_web = None
                    try:
                        self.ide_editor.grid(row=0, column=0, sticky="nsew")
                        self.ide_status_label.configure(text=f"Monaco host unavailable · native editor restored · {payload}", fg=YELLOW)
                    except Exception:
                        pass
                elif kind == "forge-intake-background":
                    result = payload or {}
                    ingested = result.get("ingested") or []
                    artifacts = result.get("artifacts") or []
                    reviews = result.get("reviews") or []
                    errors = result.get("errors") or []
                    queued = [item for item in ingested if str(item.get("state") or "").upper() == "QUEUED"]
                    available = [item for item in ingested if str(item.get("state") or "").upper() == "AVAILABLE"]
                    review_items = [item for item in ingested if str(item.get("state") or "").upper() == "REVIEW"]
                    for item in queued:
                        self._append_log(f"[PASS] Vault root-drop queued {item.get('patch_id')} for {item.get('target_project')}\n", "pass")
                    if available:
                        self._append_log(f"[INFO] Vault Downloads cataloged {len(available)} available patch(es); none were queued for application.\n", "info")
                    if reviews or review_items:
                        self._append_log(f"[INFO] Vault intake moved {len(reviews) + len(review_items)} non-executable/rejected transport(s) to Artifact Central review.\n", "info")
                    for item in artifacts:
                        self._append_log(f"[PASS] Artifact Central archived {item.get('source_name') or item.get('artifactPath')} -> {item.get('project_id') or item.get('projectId')} / {item.get('category')}\n", "pass")
                    if errors:
                        self._append_log(f"[WARN] Vault trusted-root intake has {len(errors)} blocking error(s); open Updates for details.\n", "warn")
                    self._refresh_projects()
                    self._refresh_status_async()
                elif kind == "forge-intake-background-error":
                    self._append_log(f"[WARN] Vault intake watcher scan failed: {payload}\n", "warn")
                elif kind == "forge-intake-done":
                    result = payload or {}
                    ingested = result.get("ingested") or []
                    artifacts = result.get("artifacts") or []
                    reviews = result.get("reviews") or []
                    skipped = result.get("skipped") or []
                    errors = result.get("errors") or []
                    queued = [item for item in ingested if str(item.get("state") or "").upper() == "QUEUED"]
                    available = [item for item in ingested if str(item.get("state") or "").upper() == "AVAILABLE"]
                    review_items = [item for item in ingested if str(item.get("state") or "").upper() == "REVIEW"]
                    for item in queued:
                        self._append_log(f"[PASS] Vault root-drop queued {item.get('patch_id')} for {item.get('target_project')}\n", "pass")
                    if available:
                        self._append_log(f"[INFO] Vault Downloads cataloged {len(available)} available patch(es); explicit root-drop/approval is required before application.\n", "info")
                    if reviews or review_items:
                        self._append_log(f"[INFO] Vault moved {len(reviews) + len(review_items)} transport(s) to Artifact Central review; they are non-executable.\n", "info")
                    for item in artifacts:
                        self._append_log(f"[PASS] Artifact Central archived {item.get('source_name') or item.get('artifactPath')} -> {item.get('project_id') or item.get('projectId')} / {item.get('category')}\n", "pass")
                    for item in errors:
                        self._append_log(f"[WARN] Trusted-root intake rejected {item.get('path')}: {item.get('error')}\n", "warn")
                    self._append_log(f"[INFO] Vault intake complete: {len(queued)} queued root patch(es), {len(available)} available download(s), {len(reviews) + len(review_items)} review item(s), {len(artifacts)} artifact(s) archived, {len(skipped)} waiting/skipped, {len(errors)} trusted-root error(s).\n", "info")
                    self._refresh_projects()
                    self._refresh_status_async()
                    self._popup("Vault Intake", f"Queued root patches: {len(queued)}\nAvailable downloads: {len(available)}\nReview: {len(reviews) + len(review_items)}\nWaiting/skipped: {len(skipped)}\nBlocking root errors: {len(errors)}", kind="success" if not errors else "warning")
                elif kind == "forge-intake-error":
                    self._append_log(f"[FAIL] Vault intake failed: {payload}\n", "fail")
                    self._popup("Vault Intake", str(payload), kind="error")
                elif kind == "onboard-error":
                    root, detail = payload
                    self._append_log(f"[WARN] Project onboarding catalog incomplete: {root}: {detail}\n", "warn")
                    self._refresh_projects()
                elif kind == "universal-build-log":
                    line = str(payload)
                    up = line.upper()
                    tag = "fail" if "[FAIL]" in up else ("warn" if "[WARN]" in up else ("pass" if "[PASS]" in up else ""))
                    self._append_log(line, tag)
                elif kind == "universal-build-done":
                    result = payload or {}
                    self._busy = False
                    failed = int(result.get("failed") or 0)
                    passed = int(result.get("passed") or 0)
                    skipped = int(result.get("skipped") or 0)
                    color = GREEN if failed == 0 else RED
                    state = "PASS" if failed == 0 else "FAIL"
                    self.operation_label.configure(text=f"Last: build-all {state}", fg=color)
                    self.console_job_label.configure(text=f"Last: build-all {state}", fg=color)
                    self._append_log(f"=== END UNIVERSAL BUILD MATRIX: {passed} PASS / {failed} FAIL / {skipped} SKIP ===\n", "pass" if failed == 0 else "fail")
                    self._refresh_projects()
                elif kind == "universal-build-error":
                    self._busy = False
                    self.operation_label.configure(text="Last: build-all FAIL", fg=RED)
                    self.console_job_label.configure(text="Last: build-all FAIL", fg=RED)
                    self._append_log(f"[FAIL] Universal build matrix: {payload}\n", "fail")
                    self._popup("Build All Failed", str(payload), kind="error")
                elif kind == "tooling-audit-done":
                    root, result = payload
                    if Path(root).resolve() == self.root_path.resolve():
                        domains = result.get("domains") or {}
                        cli = result.get("cli") or {}
                        scripts = result.get("scripts") or []
                        blender_scripts = result.get("blenderScripts") or []
                        ready_cli = [name for name, info in cli.items() if (info or {}).get("ready")]
                        lines = [
                            f"Project : {self.contract.name}",
                            f"Root    : {self.root_path}",
                            f"Scripts : {len(scripts)}",
                            f"Blender : {len(blender_scripts)} script(s)",
                            f"CLI     : {', '.join(ready_cli) if ready_cli else 'none detected'}",
                            "",
                            "DOMAINS",
                        ]
                        lines.extend(f"  {name:<18} {count}" for name, count in sorted(domains.items()))
                        if blender_scripts:
                            lines += ["", "BLENDER TOOLS"] + [f"  {row.get('path')}" for row in blender_scripts[:60]]
                        self._tooling_set_text("\n".join(lines) + "\n")
                        try:
                            report_dir = ensure_artifact_project_tree(self.contract.project_id)["reports"] / "tooling"
                            report_dir.mkdir(parents=True, exist_ok=True)
                            report = report_dir / "latest-tooling-audit.json"
                            report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                            self._append_log(f"[PASS] Tooling audit: {len(scripts)} script(s), {len(domains)} domain(s) · {report}\n", "pass")
                        except Exception as exc:
                            self._append_log(f"[WARN] Tooling audit report could not be persisted: {exc}\n", "warn")
                elif kind == "tooling-audit-error":
                    root, detail = payload
                    if Path(root).resolve() == self.root_path.resolve():
                        self._tooling_set_text(f"Tooling audit failed:\n{detail}\n")
                        self._append_log(f"[FAIL] Tooling audit: {detail}\n", "fail")
                elif kind == "tooling-all-done":
                    result = payload or {}
                    lines = [
                        f"Registered projects : {result.get('projectCount', 0)}",
                        f"Discovered scripts  : {result.get('scriptCount', 0)}",
                        f"Blender scripts     : {result.get('blenderScriptCount', 0)}",
                        f"Global index        : {result.get('report', '')}",
                        "",
                        "DOMAINS",
                    ]
                    lines.extend(f"  {name:<18} {count}" for name, count in (result.get("domains") or {}).items())
                    self._tooling_set_text("\n".join(lines) + "\n")
                    self._append_log(f"[PASS] Global tooling index: {result.get('projectCount',0)} project(s), {result.get('scriptCount',0)} script(s).\n", "pass")
                elif kind == "tooling-all-error":
                    self._tooling_set_text(f"Global tooling audit failed:\n{payload}\n")
                    self._append_log(f"[FAIL] Global tooling audit: {payload}\n", "fail")
                elif kind == "vault-progress":
                    files = int((payload or {}).get("files") or 0)
                    hashed = int((payload or {}).get("hashed") or 0)
                    reused = int((payload or {}).get("reusedHashes") or 0)
                    self.vault_scan_status.configure(text=f"Scanning {files} files · {hashed} hashed · {reused} cached", fg=CYAN)
                elif kind == "vault-done":
                    root, summary = payload
                    self._vault_busy = False
                    if Path(root).resolve() == self.root_path.resolve():
                        self.vault_scan_status.configure(text=f"PASS · {summary.get('files', 0)} files · {summary.get('elapsedSeconds', 0)}s", fg=GREEN)
                        self._vault_render_summary(summary)
                        self._vault_refresh_tree()
                    self._append_log(f"[PASS] Vault Library catalog scan complete: {root} ({summary.get('files', 0)} files)\n", "pass")
                elif kind == "vault-error":
                    self._vault_busy = False
                    self.vault_scan_status.configure(text="Scan failed", fg=RED)
                    self._append_log(f"[FAIL] Vault Library scan: {payload}\n", "fail")
                    self._popup("Vault Scan Failed", str(payload), kind="error")
                elif kind == "vault-storage-progress":
                    info = payload or {}
                    self.vault_scan_status.configure(
                        text=f"Migrating Vault · {int(info.get('files') or 0)} files · {int(info.get('copied') or 0)} copied · {int(info.get('reused') or 0)} verified",
                        fg=CYAN,
                    )
                elif kind == "vault-storage-done":
                    result = payload or {}
                    self.vault_scan_status.configure(text="Vault home migration PASS", fg=GREEN)
                    self._refresh_location_labels()
                    self._append_log(f"[PASS] Vault home migrated to {result.get('target')} · {result.get('files', 0)} files verified.\n", "pass")
                    self._popup("Forge Home Migrated", f"Vault now uses:\n{result.get('target')}\n\nOld data was retained for rollback.\nReceipt: {result.get('receipt')}", kind="success")
                elif kind == "vault-storage-error":
                    self.vault_scan_status.configure(text="Vault home migration failed", fg=RED)
                    self._append_log(f"[FAIL] Vault home migration: {payload}\n", "fail")
                    self._popup("Forge Home Migration Failed", str(payload), kind="error")
                elif kind == "project-migration-progress":
                    info = payload or {}
                    phase = str(info.get("phase") or "copying")
                    self.vault_scan_status.configure(
                        text=f"Project migration · {phase} · {int(info.get('files') or 0)} files · {int(info.get('copied') or 0)} copied",
                        fg=CYAN,
                    )
                elif kind == "project-migration-done":
                    self._project_migration_busy = False
                    result = payload or {}
                    source = Path(str(result.get("source") or self.root_path))
                    target = Path(str(result.get("target") or ""))
                    try:
                        self.registry.relocate(source, target, make_active=True)
                        self.vault_scan_status.configure(text="Project migration PASS", fg=GREEN)
                        self._append_log(f"[PASS] Portable project migration: {source} -> {target} · {result.get('verifiedFiles', result.get('files', 0))} files verified.\n", "pass")
                        self._popup("Project Migrated", f"Portable project copy is ready:\n{target}\n\nOriginal retained:\n{source}\n\nReceipt: {result.get('receipt')}", kind="success")
                        self._activate_project(target)
                    except Exception as exc:
                        self._append_log(f"[FAIL] Project copied but registry rebind failed: {exc}\n", "fail")
                        self._popup("Project Registry Rebind Failed", f"The verified copy exists at:\n{target}\n\nRegistry error: {exc}", kind="error")
                elif kind == "project-migration-error":
                    self._project_migration_busy = False
                    self.vault_scan_status.configure(text="Project migration failed", fg=RED)
                    self._append_log(f"[FAIL] Portable project migration: {payload}\n", "fail")
                    self._popup("Project Migration Failed", str(payload), kind="error")
                elif kind == "drive-scan-progress":
                    info = payload or {}
                    self.vault_scan_status.configure(text=f"Drive scan · {int(info.get('directories') or 0)} dirs · {int(info.get('projects') or 0)} projects", fg=CYAN)
                elif kind == "drive-scan-done":
                    self._drive_scan_busy = False
                    result = payload or {}
                    self.vault_scan_status.configure(text=f"Drive scan PASS · {result.get('projects', 0)} projects", fg=GREEN)
                    self._append_log(f"[PASS] Drive project index: {result.get('projects', 0)} projects across {result.get('directories', 0)} directories.\n", "pass")
                    self._popup("Drive Scan Complete", f"Projects discovered: {result.get('projects', 0)}\nDirectories inspected: {result.get('directories', 0)}\nDatabase: {result.get('database')}", kind="success")
                elif kind == "drive-scan-error":
                    self._drive_scan_busy = False
                    self.vault_scan_status.configure(text="Drive scan failed", fg=RED)
                    self._append_log(f"[FAIL] Drive project scan: {payload}\n", "fail")
                    self._popup("Drive Scan Failed", str(payload), kind="error")
                elif kind == "source-status":
                    info = payload or {}
                    if hasattr(self, "source_status_label"):
                        if not info.get("gitReady"):
                            self.source_status_label.configure(text="Git repository not initialized. Use Initialize Git below.", fg=YELLOW)
                        else:
                            remotes = info.get("remotes") or []
                            gh = sorted({str(x.get("name")) for x in remotes if x.get("kind") == "github"})
                            fj = sorted({str(x.get("name")) for x in remotes if x.get("kind") == "forgejo"})
                            dirty = int(info.get("staged") or 0) + int(info.get("unstaged") or 0) + int(info.get("untracked") or 0)
                            sync = "upstream unknown" if info.get("ahead") is None else f"{info.get('ahead')} ahead / {info.get('behind')} behind"
                            self.source_status_label.configure(
                                text=(f"Branch {info.get('branch') or '<detached>'} @ {info.get('headShort') or '<no commit>'}  ·  "
                                      f"{'clean' if not dirty else str(dirty) + ' changed'}  ·  {sync}\n"
                                      f"GitHub: {', '.join(gh) if gh else 'not configured'}  ·  Forgejo: {', '.join(fj) if fj else 'not configured'}"),
                                fg=GREEN if not dirty else YELLOW,
                            )
                elif kind == "source-status-error":
                    if hasattr(self, "source_status_label"):
                        self.source_status_label.configure(text=f"Source status unavailable: {payload}", fg=RED)
                elif kind == "forgejo-status":
                    info = payload or {}
                    self._forgejo_status = dict(info)
                    ready = "Ready" if info.get("binaryReady") else "Missing binary"
                    online = f"Online {info.get('serverVersion') or ''}".strip() if info.get("online") else "Offline"
                    token = "API token ready" if info.get("tokenConfigured") else "API token not configured"
                    color = GREEN if info.get("online") else (YELLOW if info.get("binaryReady") else RED)
                    self.forgejo_status_label.configure(
                        text=f"{ready}  ·  {online}  ·  {token}\n{info.get('url') or ''}  ·  {info.get('workPath') or ''}\n{info.get('binaryVersion') or ''}",
                        fg=color,
                    )
                elif kind == "forgejo-status-error":
                    self.forgejo_status_label.configure(text=f"Forgejo status unavailable: {payload}", fg=RED)
                elif kind == "status":
                    self._render_status(payload)
                elif kind == "status-error":
                    self.refresh_btn.configure(state="normal")
                    self.footer.configure(text="[Status:Unavailable]", fg=RED)
                    self._append_log(f"Status refresh failed: {payload}\n", "fail")
        except queue.Empty:
            pass
        self.window.after(60, self._drain_events)

    # ------------------------------------------------------------------
    # Windows tray / background services / active health
    # ------------------------------------------------------------------
    def _start_tray(self) -> None:
        if not tray_supported():
            return
        try:
            self._tray = ForgeTray(lambda key: self._event_q.put(("tray-command", key)), tooltip=f"Forge — {self.contract.name}")
            if self._tray.start():
                self._tray.set_status(f"Forge — {self.contract.name}")
                self._append_log("[PASS] Windows system-tray service ready.\n", "pass")
            else:
                self._tray = None
                self._append_log("[WARN] Windows system-tray service could not start.\n", "warn")
        except Exception as exc:
            self._tray = None
            self._append_log(f"[WARN] Windows system-tray service: {exc}\n", "warn")

    def _show_from_tray(self) -> None:
        try:
            self.window.deiconify()
            self.window.state("normal")
            self.window.lift()
            self.window.focus_force()
        except Exception:
            pass

    def _hide_to_tray(self) -> None:
        if self._tray is None or not self._tray.running:
            try: self.window.iconify()
            except Exception: pass
            return
        try:
            self.window.withdraw()
            cfg = load_settings().get("ui") or {}
            if bool(cfg.get("showTrayNotifications", True)):
                self._tray.notify("Forge", "Forge is still running in the system tray.")
        except Exception:
            pass

    def _on_window_unmap(self, _event: Any = None) -> None:
        if self._exit_requested:
            return
        cfg = load_settings().get("ui") or {}
        if not bool(cfg.get("minimizeToTray", True)) or self._tray is None:
            return
        try:
            if self.window.state() == "iconic":
                self.window.after(40, self._hide_to_tray)
        except Exception:
            pass

    def _handle_tray_command(self, key: str) -> None:
        key = str(key or "")
        if key == "open": self._show_from_tray()
        elif key == "projects": self._show_from_tray(); self._show_app_tab("Projects")
        elif key == "workspace": self._show_from_tray(); self._show_app_tab("Project Workspace")
        elif key == "health": self._show_from_tray(); self._set_health_rail_collapsed(False)
        elif key == "full-gate": self._show_from_tray(); self._show_app_tab("Project Workspace"); self._start_command("full")
        elif key == "apply-updates": self._show_from_tray(); self._apply_updates()
        elif key == "scan-intake": self._vault_scan_intake()
        elif key == "source-control": self._show_from_tray(); self._show_app_tab("Project Workspace"); self._show_page("Source Control")
        elif key == "forgejo": self._show_from_tray(); self._show_app_tab("Forgejo")
        elif key == "ide": self._show_from_tray(); self._show_app_tab("IDE")
        elif key == "cortex": self._show_from_tray(); self._show_app_tab("Cortex")
        elif key == "settings": self._show_from_tray(); self._show_app_tab("Settings")
        elif key == "open-home": open_path(vault_data_root())
        elif key == "open-artifacts": open_path(artifact_central_root())
        elif key == "exit": self._exit_vault()

    def _exit_vault(self) -> None:
        self._exit_requested = True
        self._on_close()

    def _start_configured_services(self) -> None:
        services = load_settings().get("services") or {}
        if bool(services.get("forgejoAutoStart", False)):
            self.window.after(900, lambda: self._start_builtin_forgejo("start") if not self._busy else None)
        if bool(services.get("cortexAutoStart", False)):
            self.window.after(1500, self._cortex_start)

    def _schedule_health_refresh(self) -> None:
        if self._exit_requested:
            return
        root = self.root_path
        contract = self.contract
        if not self._active_health_scan_running:
            self._active_health_scan_running = True

            def work() -> None:
                try:
                    health = evaluate_project(root, contract)
                    self._event_q.put(("active-health", (root, health)))
                except Exception as exc:
                    self._event_q.put(("active-health-error", (root, str(exc))))
                finally:
                    self._event_q.put(("active-health-idle", root))

            threading.Thread(target=work, daemon=True, name="ForgeActiveHealth").start()
        try:
            seconds = max(5, int(float((load_settings().get("ui") or {}).get("healthRefreshSeconds", 10) or 10)))
        except Exception:
            seconds = 10
        self.window.after(seconds * 1000, self._schedule_health_refresh)

    def _offer_restart_if_updated(self) -> None:
        marker = restart_marker_path()
        if not marker.is_file():
            return
        try:
            data = json.loads(marker.read_text(encoding="utf-8-sig"))
        except Exception:
            data = {}
        patch_id = str(data.get("patchId") or "Forge update")
        title = str(data.get("title") or "").strip()
        detail = patch_id + (f" — {title}" if title and title != patch_id else "")
        if not self._popup(
            "Forge Restart Required",
            f"{detail} was applied successfully.\n\nRestart Forge now to load the updated application code?",
            kind="success",
            confirm=True,
        ):
            self._append_log("[INFO] Forge update applied; restart is still required before the new code is active.\n", "info")
            return
        try:
            marker.unlink(missing_ok=True)
            app_root = Path(__file__).resolve().parents[1]
            launcher = app_root / "Forge.vbs"
            if os.name == "nt" and launcher.is_file():
                os.startfile(str(launcher))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(
                    [sys.executable, str(app_root / "app" / "ForgeStandalone.py"), "--root", str(self.root_path)],
                    cwd=str(app_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            self._intake_stop.set()
            self.window.after(120, self.window.destroy)
        except Exception as exc:
            self._append_log(f"[WARN] Forge update is applied but automatic restart failed: {exc}\n", "warn")
            self._popup("Forge Restart", f"The update is applied, but automatic restart failed.\n\n{exc}\n\nClose and reopen Vault manually.", kind="warning")

    def _latest_applied_patch_identity(self) -> tuple[str, str] | None:
        """Return the newest successfully applied patch identity for commit-message carry-forward."""
        receipts = self.root_path / "artifacts" / "patches" / "receipts"
        if not receipts.is_dir():
            return None
        candidates: list[tuple[float, str, str]] = []
        for path in receipts.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            if str(data.get("status") or "").strip().casefold() != "applied":
                continue
            patch_id = str(data.get("patchId") or "").strip()
            if not patch_id:
                continue
            title = str(data.get("title") or "").strip()
            try:
                stamp = path.stat().st_mtime
            except OSError:
                stamp = 0.0
            candidates.append((stamp, patch_id, title))
        if not candidates:
            return None
        _stamp, patch_id, title = max(candidates, key=lambda row: row[0])
        return patch_id, title

    def _green_commit_default(self) -> tuple[str, str]:
        patch = self._latest_applied_patch_identity()
        if patch:
            patch_id, title = patch
            subject = f"{self.contract.name} GREEN {patch_id}"
            if title:
                subject += f" - {title}"
            return subject, f"Current applied patch: {patch_id}" + (f" — {title}" if title else "")
        marker = self.root_path / ".cortex" / "last-green-quality-gate.json"
        if marker.is_file():
            try:
                data = json.loads(marker.read_text(encoding="utf-8-sig"))
                head = str(data.get("gitHead") or "").strip()[:12]
                created = str(data.get("createdUtc") or "").strip()
                basis = "Current certified GREEN source"
                if head:
                    basis += f" @ {head}"
                if created:
                    basis += f" ({created})"
                return f"{self.contract.name} GREEN checkpoint - {datetime.now().strftime('%Y-%m-%d %H:%M')}", basis
            except Exception:
                pass
        return (
            f"{self.contract.name} GREEN checkpoint - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "Current certified GREEN source",
        )


    def _ask_commit_message(self, *, push: bool) -> str | None:
        tk = self.tk
        default, basis = self._green_commit_default()
        dialog = tk.Toplevel(self.window)
        dialog.withdraw()
        dialog.configure(bg=BG)
        dialog.overrideredirect(True)
        dialog.transient(self.window)
        dialog.resizable(False, False)

        outer = tk.Frame(dialog, bg=CYAN, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        shell = tk.Frame(outer, bg=PANEL)
        shell.pack(fill="both", expand=True)

        result: list[str | None] = [None]

        def close(value: str | None) -> None:
            result[0] = value
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()

        titlebar = tk.Frame(shell, bg=PANEL_2, height=44)
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)
        tk.Label(
            titlebar,
            text="COMMIT + PUSH CERTIFIED GREEN" if push else "COMMIT CERTIFIED GREEN",
            bg=PANEL_2,
            fg=TEXT,
            font=("Segoe UI Semibold", 12),
        ).pack(side="left", padx=16)
        close_btn = tk.Button(
            titlebar,
            text="×",
            command=lambda: close(None),
            bg=PANEL_2,
            fg=MUTED,
            activebackground=RED,
            activeforeground=TEXT,
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("Segoe UI Semibold", 15),
            width=3,
        )
        close_btn.pack(side="right", fill="y")

        header = tk.Frame(shell, bg=PANEL)
        header.pack(fill="x", padx=18, pady=(14, 8))
        tk.Label(
            header,
            text=f"{self.contract.name}  ·  {basis}",
            bg=PANEL,
            fg=GREEN,
            font=("Segoe UI", 9),
            wraplength=700,
            justify="left",
        ).pack(anchor="w")

        git = self._last_status.get("git") or {}
        green_state = "MATCH" if git.get("greenMatch") else ("STALE" if git.get("greenMarker") else "NONE")
        branch = str(git.get("branch") or "unknown")
        ahead = git.get("ahead")
        behind = git.get("behind")
        sync = "unknown" if ahead is None or behind is None else (f"{ahead} ahead / {behind} behind")
        statebar = tk.Frame(shell, bg=PANEL_2)
        statebar.pack(fill="x", padx=18, pady=(0, 10))
        for label, value, color in (
            ("GREEN", green_state, GREEN if green_state == "MATCH" else YELLOW),
            ("Branch", branch, TEXT),
            ("Sync", sync, GREEN if ahead == 0 and behind == 0 else YELLOW),
        ):
            cell = tk.Frame(statebar, bg=PANEL_2)
            cell.pack(side="left", padx=12, pady=7)
            tk.Label(cell, text=label, bg=PANEL_2, fg=MUTED, font=("Segoe UI", 7)).pack(anchor="w")
            tk.Label(cell, text=value, bg=PANEL_2, fg=color, font=("Segoe UI Semibold", 9)).pack(anchor="w")

        body = tk.Frame(shell, bg=PANEL)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        tk.Label(body, text="Commit message", bg=PANEL, fg=MUTED, font=("Segoe UI Semibold", 9)).pack(anchor="w")
        editor_frame = tk.Frame(body, bg="#07090b", highlightthickness=1, highlightbackground=BORDER)
        editor_frame.pack(fill="both", expand=True, pady=(6, 0))
        editor = tk.Text(
            editor_frame,
            bg="#07090b",
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#21404a",
            selectforeground=TEXT,
            bd=0,
            relief="flat",
            font=("Consolas", 10),
            wrap="word",
            undo=True,
            height=12,
        )
        scroll = tk.Scrollbar(editor_frame, command=editor.yview, bg=PANEL)
        editor.configure(yscrollcommand=scroll.set)
        editor.pack(side="left", fill="both", expand=True, padx=(11, 0), pady=10)
        scroll.pack(side="right", fill="y", padx=(5, 8), pady=8)
        editor.insert("1.0", default)
        editor.tag_add("sel", "1.0", "end-1c")

        def accept() -> None:
            message = editor.get("1.0", "end-1c").strip()
            if not message:
                self._popup("Commit Certified GREEN", "Enter a commit message before continuing.", kind="warning", parent=dialog)
                editor.focus_set()
                return
            close(message)

        actions = tk.Frame(shell, bg=PANEL)
        actions.pack(fill="x", padx=18, pady=(0, 16))
        tk.Label(actions, text="Esc = Cancel  ·  Ctrl+Enter = Commit", bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")
        self._button(actions, "Cancel", lambda: close(None), compact=True).pack(side="right", padx=(8, 0))
        self._button(
            actions,
            "Commit + Push GREEN" if push else "Commit GREEN",
            accept,
            primary=True,
            compact=True,
        ).pack(side="right")

        dialog.bind("<Escape>", lambda _e: close(None))
        dialog.bind("<Control-Return>", lambda _e: accept())
        dialog.protocol("WM_DELETE_WINDOW", lambda: close(None))
        self._center_modal(dialog, 760, 455)
        self._round_window(dialog)
        dialog.deiconify()
        dialog.lift()
        dialog.grab_set()
        editor.focus_force()
        self.window.wait_window(dialog)
        return result[0]

    def _commit_green(self) -> None:
        message = self._ask_commit_message(push=False)
        if message:
            self._start_command("commit-green", ["--message", message], label="commit-green")

    def _commit_push_green(self) -> None:
        message = self._ask_commit_message(push=True)
        if message and self._popup(
            "Commit + Push GREEN",
            "Commit the current certified GREEN source and push it to the configured remote?",
            kind="warning",
            confirm=True,
        ):
            self._start_command("commit-push-green", ["--message", message], label="commit-push-green")

    def _apply_updates(self) -> None:
        if self._popup("Apply Validated Updates", "Apply the currently validated Vault update queue? Invalid updates remain fail-closed.", kind="warning", confirm=True):
            self._start_command("patch-apply", ["--yes"], label="apply-updates")

    def _open_latest_debug(self) -> None:
        path = latest_debug_bundle(self.root_path)
        if path:
            reveal_file(path)
        else:
            open_path(self.root_path / "artifacts" / "debug")

    def _open_cli(self) -> None:
        control = self.contract.raw.get("root_control_center") or {}
        declared = str(control.get("launcher") or "").strip()
        candidates = []
        if declared:
            candidates.append(self.root_path / declared)
        candidates.extend([
            self.root_path / "PROJECT_CONTROL_CENTER.cmd",
            *sorted(self.root_path.glob("*Tools.cmd")),
            *sorted(self.root_path.glob("*ControlCenter.cmd")),
        ])
        launcher = next((path for path in candidates if path.is_file()), None)
        if os.name == "nt" and launcher is not None:
            # Root launchers own their own interactive syntax; do not force Cortex's --cli
            # switch onto legacy/adopted project utilities.
            argv = ["cmd.exe", "/k", str(launcher)]
            if launcher.name.casefold() == "project_control_center.cmd":
                argv.append("--cli")
            subprocess.Popen(argv, cwd=str(self.root_path), creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
            return
        self._popup("Forge", "No interactive project launcher was discovered for the selected project.")

    def _on_close(self) -> None:
        ui = load_settings().get("ui") or {}
        if not self._exit_requested and bool(ui.get("closeToTray", True)) and self._tray is not None and self._tray.running:
            self._hide_to_tray()
            return
        if self._active_proc and self._active_proc.poll() is None:
            if not self._popup("Active Forge Job", "A Forge job is still running. Stop it and exit Forge?", kind="warning", confirm=True):
                self._exit_requested = False
                return
            terminate_process_tree(self._active_proc)
        self._intake_stop.set()
        if self._tray is not None:
            try: self._tray.stop()
            except Exception: pass
            self._tray = None
        self.window.destroy()

    def run(self) -> int:
        self.window.mainloop()
        return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Universal Forge GUI")
    p.add_argument("--root")
    p.add_argument("--self-test", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_root(args.root)
    if args.self_test:
        for note in validate_surface(root):
            print(f"PASS {note}")
        registry = ProjectRegistry()
        registry.register(root, make_active=False)
        print(f"PASS registry={registry.path}")
        print(f"PASS registered-projects={len(registry.entries())}")
        try:
            import tkinter as tk
            print(f"PASS tkinter={tk.TkVersion}")
        except Exception as exc:
            raise SurfaceError(f"Tkinter GUI runtime is unavailable: {exc}") from exc
        print(f"PASS gui-version={GUI_VERSION}")
        return 0
    return ForgeGui(root).run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SurfaceError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
