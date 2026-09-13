#!/usr/bin/env python3
"""ForgePY F416-F440 normalization layer.

This module intentionally builds on the GREEN F60R415 runtime instead of forking a
second application shell.  It centralizes command projection, Updates, Operations,
Local Source recovery, the native IDE, and selected-project state while preserving
ForgePY's existing providers, transactional patch engine, Vault and health authorities.
"""
from __future__ import annotations

import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

NORMALIZATION_VERSION = "FORGEPY-NORMALIZATION-F445-F449-CANDIDATE"
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

CATEGORY_ORDER = (
    "Build & Certification",
    "Run & Debug",
    "Content & Assets",
    "World & Data",
    "Packaging & Release",
    "Maintenance",
    "Development",
    "Advanced",
)


@dataclass(frozen=True)
class ForgeCommandSpec:
    command_id: str
    label: str
    category: str
    description: str = ""
    risk: str = "read-only"
    provider_key: str = ""
    source: str = "project"
    tool: Any = None
    hidden_from_operations: bool = False


def _log(gui: Any, message: str, tag: str = "info") -> None:
    try:
        gui._append_log(str(message).rstrip("\n") + "\n", tag)
    except Exception:
        pass


def _dispatch(gui: Any, func: Callable[[], None]) -> None:
    q = getattr(gui, "_forge_main_actions", None)
    if q is not None:
        try:
            q.put(func)
            return
        except Exception:
            pass
    try:
        gui.window.after(0, func)
    except Exception:
        pass


def _project_aliases(gui: Any) -> set[str]:
    root = Path(gui.root_path).expanduser().resolve()
    return {
        str(getattr(gui.contract, "project_id", "") or "").strip().casefold(),
        str(getattr(gui.contract, "name", "") or "").strip().casefold(),
        root.name.casefold(),
        str(root).casefold(),
    } - {""}


def _item_belongs(gui: Any, item: dict[str, Any]) -> bool:
    target = str(item.get("target_project") or "").strip().casefold()
    return bool(target and target in _project_aliases(gui))


def _git(root: Path, *args: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    startup = None
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
        startup.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
    return subprocess.run(
        [shutil.which("git") or "git", "-C", str(root), *map(str, args)],
        cwd=str(root), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=timeout,
        creationflags=flags, startupinfo=startup,
    )


def _git_lines(root: Path, *args: str) -> list[str]:
    cp = _git(root, *args)
    return [line.rstrip() for line in cp.stdout.splitlines() if line.strip()] if cp.returncode == 0 else []


def _safe_ref_component(value: str) -> str:
    value = str(value or "main").strip().replace("\\", "/")
    value = re.sub(r"[^A-Za-z0-9._/-]+", "-", value).strip("-./")
    value = re.sub(r"/{2,}", "/", value)
    return value or "main"


def _branch(root: Path) -> str:
    cp = _git(root, "branch", "--show-current", timeout=15)
    return cp.stdout.strip() if cp.returncode == 0 and cp.stdout.strip() else "main"


def recovery_ref(root: Path, branch: str | None = None) -> str:
    return f"refs/forgepy/recovery/{_safe_ref_component(branch or _branch(root))}"


def recovery_sha(root: Path, branch: str | None = None) -> str:
    cp = _git(root, "rev-parse", "--verify", recovery_ref(root, branch), timeout=15)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def ensure_recovery_ref(root: Path, branch: str | None = None) -> str:
    branch = branch or _branch(root)
    ref = recovery_ref(root, branch)
    if recovery_sha(root, branch):
        return ref
    head = _git(root, "rev-parse", "--verify", "HEAD", timeout=15)
    if head.returncode == 0 and head.stdout.strip():
        _git(root, "update-ref", ref, head.stdout.strip(), timeout=15)
    return ref


def advance_recovery(root: Path, branch: str | None = None) -> str:
    """Advance the rolling recovery ref to the current certified HEAD."""
    branch = branch or _branch(root)
    head = _git(root, "rev-parse", "--verify", "HEAD", timeout=15)
    if head.returncode != 0 or not head.stdout.strip():
        return ""
    ref = recovery_ref(root, branch)
    cp = _git(root, "update-ref", ref, head.stdout.strip(), timeout=15)
    return ref if cp.returncode == 0 else ""


def _category_for(key: str, label: str = "") -> str:
    low = f"{key} {label}".casefold()
    if any(x in low for x in ("asset", "blender", "blockbench", "texture", "mesh", "audio", "sprite", "atlas", "cook", "import", "export", "model")):
        return "Content & Assets"
    if any(x in low for x in ("world", "terrain", "scene", "map", "pcg", "cave", "database", "db.", "migration", "migrate", "save", "hydrology", "city", "estate")):
        return "World & Data"
    if any(x in low for x in ("package", "release", "installer", "publish", "distribut", "archive-release")):
        return "Packaging & Release"
    if any(x in low for x in ("doctor", "repair", "clean", "hygiene", "dependency", "preflight", "maint", "audit")):
        return "Maintenance"
    if any(x in low for x in ("run", "launch", "play", "debug", "profile", "server", "client", "replay")):
        return "Run & Debug"
    if any(x in low for x in ("full", "gate", "build", "test", "validate", "certif", "check", "compile")):
        return "Build & Certification"
    if any(x in low for x in ("git", "source", "patch", "update", "commit", "push", "pull", "branch", "remote")):
        return "Advanced"
    if any(x in low for x in ("dev", "generate", "scaffold", "tool", "handoff")):
        return "Development"
    return "Advanced"


def _risk_normalized(value: str) -> str:
    low = str(value or "").strip().casefold()
    if any(x in low for x in ("destructive", "danger", "delete", "reset")):
        return "destructive"
    if any(x in low for x in ("write", "mutat", "change", "apply", "install")):
        return "writes-project"
    if any(x in low for x in ("network", "remote", "push", "publish")):
        return "network"
    return "read-only"


def _project_commands(gui: Any) -> list[ForgeCommandSpec]:
    rows: list[ForgeCommandSpec] = []
    seen: set[str] = set()
    common = {
        "full": ("Full Gate", "Build & Certification", "Run the authoritative project Full Gate."),
        "build": ("Build", "Build & Certification", "Run the project default build."),
        "launch-gui": ("Run", "Run & Debug", "Launch the project's normal GUI/runtime."),
        "debug-bundle": ("Debug Bundle", "Run & Debug", "Create the canonical debug handoff."),
        "doctor": ("Doctor", "Maintenance", "Run project diagnostics/preflight."),
    }
    for key, (label, category, desc) in common.items():
        try:
            supported = bool(gui.backend and gui.backend.supports(key))
        except Exception:
            supported = False
        if supported:
            rows.append(ForgeCommandSpec(
                f"project.{key}", label, category, desc,
                risk="writes-project" if key in {"full", "build"} else "read-only",
                provider_key=key, source="universal",
                hidden_from_operations=key in {"full", "build", "launch-gui"},
            ))
            seen.add(key.casefold())

    for item in list(getattr(gui.contract, "commands", ()) or ()):
        key = str(getattr(item, "key", "") or "").strip()
        if not key or key.casefold() in seen:
            continue
        label = str(getattr(item, "label", "") or key).strip()
        risk = _risk_normalized(str(getattr(item, "risk", "") or ""))
        category = _category_for(key, label)
        hidden = category == "Advanced" and any(x in key.casefold() for x in ("git.", "patch.", "source.", "update"))
        rows.append(ForgeCommandSpec(
            f"provider.{key}", label, category,
            description=f"Project provider command: {key}",
            risk=risk, provider_key=key, source="provider",
            hidden_from_operations=hidden,
        ))
        seen.add(key.casefold())

    project_id = str(getattr(gui.contract, "project_id", gui.root_path.name))
    try:
        from ForgeToolRegistry import load
        tools = list(load(project_id) or [])
    except Exception:
        tools = []
    for tool in tools:
        state = str(getattr(tool, "state", "") or "").upper()
        if state not in {"VERIFIED", "CERTIFIED"}:
            continue
        tool_id = str(getattr(tool, "tool_id", "") or getattr(tool, "name", "") or "tool").strip()
        label = str(getattr(tool, "name", "") or tool_id).strip()
        raw_category = str(getattr(tool, "category", "") or "").strip()
        category = raw_category if raw_category in CATEGORY_ORDER else _category_for(tool_id, f"{label} {raw_category}")
        risk = "writes-project" if bool(getattr(tool, "mutates", False) or getattr(tool, "destructive", False)) else "read-only"
        rows.append(ForgeCommandSpec(
            f"tool.{tool_id}", label, category,
            description=str(getattr(tool, "description", "") or getattr(tool, "capability", "") or "Certified project tool."),
            risk=risk, source="tool", tool=tool,
        ))
    return rows


class ForgeCommandRegistry:
    def __init__(self, gui: Any) -> None:
        self.gui = gui
        self._commands: dict[str, ForgeCommandSpec] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self._commands.clear()
        for row in _project_commands(self.gui):
            self._commands[row.command_id.casefold()] = row
        extras = (
            ForgeCommandSpec("forge.updates", "Check for updates", "Maintenance", "Refresh the selected project's update catalog.", source="forge", hidden_from_operations=True),
            ForgeCommandSpec("forge.project-cli", "Project CLI", "Development", "Open the project-owned CLI/control center.", source="forge", hidden_from_operations=True),
            ForgeCommandSpec("forge.command-palette", "Command Palette", "Development", "Search all registered ForgePY/project commands.", source="forge", hidden_from_operations=True),
        )
        for row in extras:
            self._commands[row.command_id.casefold()] = row

    def all(self) -> list[ForgeCommandSpec]:
        return sorted(self._commands.values(), key=lambda x: (CATEGORY_ORDER.index(x.category) if x.category in CATEGORY_ORDER else 99, x.label.casefold()))

    def get(self, command_id: str) -> ForgeCommandSpec | None:
        return self._commands.get(str(command_id or "").casefold())

    def operation_groups(self) -> dict[str, list[ForgeCommandSpec]]:
        grouped: dict[str, list[ForgeCommandSpec]] = {}
        for row in self.all():
            if row.hidden_from_operations:
                continue
            grouped.setdefault(row.category, []).append(row)
        return {category: grouped.get(category, []) for category in CATEGORY_ORDER if grouped.get(category)}

    def invoke(self, command_id: str) -> bool:
        row = self.get(command_id)
        if row is None:
            return False
        gui = self.gui
        if row.risk in {"writes-project", "destructive"}:
            warning = "This command can modify project source or generated project state."
            if row.risk == "destructive":
                warning = "This command is marked destructive by the project provider."
            if not gui._popup("Project Operation", f"{row.label}\n\n{warning}\n\nContinue?", kind="warning", confirm=True):
                return True
        if row.source == "tool" and row.tool is not None:
            try:
                import ForgeSimplifiedUX as ux
                ux._run_certified_tool(gui, row.tool)
            except Exception as exc:
                gui._popup("Project Operation", str(exc), kind="error")
            return True
        if row.command_id == "forge.updates":
            _show_updates(gui, run_scan=True)
            return True
        if row.command_id == "forge.project-cli":
            _open_project_cli_console(gui)
            return True
        if row.command_id == "forge.command-palette":
            _open_command_palette(gui)
            return True
        key = row.provider_key
        if key:
            try:
                gui._start_command(key)
            except Exception as exc:
                gui._popup("Project Operation", f"Could not start {row.label}:\n{exc}", kind="error")
            return True
        return False


def _registry(gui: Any, *, rebuild: bool = False) -> ForgeCommandRegistry:
    reg = getattr(gui, "_forge_command_registry_v1", None)
    if reg is None:
        reg = ForgeCommandRegistry(gui)
        gui._forge_command_registry_v1 = reg
    elif rebuild:
        reg.rebuild()
    return reg


def _quick_bar(gui: Any, parent: Any) -> None:
    tk = gui.tk
    quick = gui._panel(parent)
    quick.pack(fill="x", padx=10, pady=(5, 5))
    row = tk.Frame(quick, bg=PANEL)
    row.pack(fill="x", padx=8, pady=5)
    gui._forge_quick_project = tk.Label(row, text=str(gui.contract.name), bg=PANEL, fg=MUTED, font=("Segoe UI Semibold", 9), anchor="w")
    gui._forge_quick_project.pack(side="left", padx=(2, 10))
    gui._button(row, "FULL GATE", lambda: gui._start_command("full"), primary=True, compact=True).pack(side="left", padx=(0, 4))
    gui._button(row, "BUILD", lambda: gui._start_command("build"), compact=True).pack(side="left", padx=4)
    gui._button(row, "RUN", lambda: gui._start_command("launch-gui"), compact=True).pack(side="left", padx=4)
    update = gui._button(row, "Apply + Full Gate", lambda: _apply_first_ready(gui), compact=True)
    gui._forge_quick_update_button = update
    gui._button(row, "Project CLI", lambda: _open_project_cli_console(gui), compact=True).pack(side="right", padx=(4, 2))
    # Contextual only; _refresh_updates_workspace decides whether it is visible.


def _status_bar(gui: Any, parent: Any) -> None:
    tk = gui.tk
    bar = tk.Frame(parent, bg="#07090b", height=25, highlightthickness=1, highlightbackground="#20262d")
    bar.pack(fill="x", side="bottom", padx=10, pady=(0, 5))
    bar.pack_propagate(False)
    gui._forge_status_project = tk.Label(bar, text="", bg="#07090b", fg=TEXT, font=("Segoe UI", 8), anchor="w")
    gui._forge_status_project.pack(side="left", padx=(8, 8))
    gui._forge_status_git = tk.Label(bar, text="", bg="#07090b", fg=MUTED, font=("Consolas", 8), anchor="w")
    gui._forge_status_git.pack(side="left", padx=(0, 8))
    gui.footer = tk.Label(bar, text="[Status:Loading]", bg="#07090b", fg=CYAN, font=("Consolas", 8), anchor="w")
    gui.footer.pack(side="left", fill="x", expand=True)
    try:
        from ForgeApplicationIdentity import DISPLAY_VERSION, DISPLAY_BUILD
        identity = f"ForgePY {DISPLAY_VERSION} · {DISPLAY_BUILD}"
    except Exception:
        from ForgePYVersion import VERSION
        identity = f"ForgePY {VERSION}"
    tk.Label(bar, text=identity, bg="#07090b", fg=MUTED, font=("Consolas", 8)).pack(side="right", padx=(8, 10))
    gui._forge_status_last_run = tk.Label(bar, text="Last: —", bg="#07090b", fg=MUTED, font=("Consolas", 8), anchor="e")
    gui._forge_status_last_run.pack(side="right", padx=(8, 0))
    gui._forge_f440_status_bar = bar


def _console(gui: Any, console: Any) -> None:
    tk = gui.tk
    bar = tk.Frame(console, bg=PANEL)
    bar.pack(fill="x", padx=10, pady=(8, 5))
    tk.Label(bar, text="PROJECT CONSOLE", bg=PANEL, fg=CYAN, font=("Segoe UI Semibold", 9)).pack(side="left")
    gui._button(bar, "Copy All", lambda: gui._copy_all(gui.console_text), compact=True).pack(side="right", padx=(5, 0))
    gui._button(bar, "Clear", gui._clear_log, compact=True).pack(side="right", padx=(5, 0))
    gui._button(bar, "Log", gui._open_active_log, compact=True).pack(side="right", padx=(5, 0))

    body = tk.Frame(console, bg="#07090b")
    body.pack(fill="both", expand=True, padx=8, pady=(0, 4))
    gui.console_text = tk.Text(body, bg="#07090b", fg=TEXT, insertbackground=TEXT, selectbackground="#21404a", selectforeground=TEXT, bd=0, relief="flat", font=("Consolas", 9), wrap="word")
    scroll = gui.ttk.Scrollbar(body, command=gui.console_text.yview, orient="vertical")
    gui.console_text.configure(yscrollcommand=scroll.set)
    gui.console_text.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    gui._configure_log_tags(gui.console_text)

    gui.console_suggestions = tk.Listbox(console, height=7, bg="#0c1014", fg=TEXT, selectbackground="#21404a", selectforeground=TEXT, bd=0, highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 8), activestyle="none")
    gui.console_suggestions.bind("<Double-Button-1>", gui._console_accept_suggestion)
    gui.console_suggestions.bind("<Return>", gui._console_accept_suggestion)

    row = tk.Frame(console, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER)
    row.pack(fill="x", padx=8, pady=(0, 8))
    gui.console_command_row = row

    def toggle() -> None:
        visible = bool(gui.console_suggestions.winfo_manager())
        if visible:
            gui._console_hide_suggestions()
            toggle_btn.configure(text=">")
        else:
            gui._console_show_suggestions(force_all=True)
            toggle_btn.configure(text="<")

    toggle_btn = tk.Button(row, text=">", command=toggle, bg=PANEL_2, fg=CYAN, activebackground=PANEL, activeforeground=CYAN, bd=0, relief="flat", font=("Consolas", 11), cursor="hand2", width=2)
    toggle_btn.pack(side="left", padx=(6, 2), pady=2)
    gui._forge_console_toggle = toggle_btn
    gui.console_command_var = tk.StringVar()
    gui.console_command_entry = tk.Entry(row, textvariable=gui.console_command_var, bg=PANEL_2, fg=TEXT, insertbackground=CYAN, bd=0, relief="flat", font=("Consolas", 9))
    gui.console_command_entry.pack(side="left", fill="x", expand=True, ipady=7)
    gui.console_command_entry.bind("<KeyRelease>", gui._console_command_changed)
    gui.console_command_entry.bind("<Return>", gui._console_execute_entry)
    gui.console_command_entry.bind("<Tab>", gui._console_complete_entry)
    gui.console_command_entry.bind("<Down>", lambda _e: gui._console_history_move(1))
    gui.console_command_entry.bind("<Up>", lambda _e: gui._console_history_move(-1))
    gui.console_command_entry.bind("<Control-space>", lambda _e: (gui._console_show_suggestions(force_all=True), toggle_btn.configure(text="<")))
    gui.console_command_entry.bind("<Escape>", lambda _e: (gui._console_hide_suggestions(), toggle_btn.configure(text=">")))
    gui.stop_btn = gui._button(row, "Stop", gui._stop_active, compact=True, danger=True)
    gui.stop_btn.configure(state="disabled")
    gui.stop_btn.pack(side="right", padx=4, pady=3)
    gui._button(row, "Send", gui._console_execute_entry, primary=True, compact=True).pack(side="right", padx=(4, 3), pady=3)
    _refresh_console_catalog(gui)


def _refresh_console_catalog(gui: Any) -> None:
    reg = _registry(gui, rebuild=True)
    rows = [(item.command_id, f"{item.label} — {item.category}") for item in reg.all()]
    # Keep short aliases for the high-frequency provider lane.
    aliases: list[tuple[str, str]] = []
    for item in reg.all():
        if item.provider_key and item.provider_key not in {x[0] for x in aliases}:
            aliases.append((item.provider_key, item.label))
    gui._console_command_catalog = aliases + rows
    gui._console_suggestion_keys = []
    gui._console_history_index = len(getattr(gui, "_console_history", []))
    try:
        gui._console_hide_suggestions()
        if hasattr(gui, "_forge_console_toggle"):
            gui._forge_console_toggle.configure(text=">")
    except Exception:
        pass


def _console_execute(gui: Any, original: Callable[..., Any], _event: Any = None) -> str:
    raw = str(gui.console_command_var.get()).strip() if hasattr(gui, "console_command_var") else ""
    if raw:
        try:
            argv = shlex.split(raw, posix=(os.name != "nt"))
        except ValueError:
            argv = [raw]
        if argv:
            reg = _registry(gui)
            if reg.get(argv[0]):
                if raw not in gui._console_history:
                    gui._console_history.append(raw)
                gui.console_command_var.set("")
                gui._console_hide_suggestions()
                if hasattr(gui, "_forge_console_toggle"):
                    gui._forge_console_toggle.configure(text=">")
                reg.invoke(argv[0])
                return "break"
    return original(gui, _event)


def _open_command_palette(gui: Any) -> None:
    tk = gui.tk
    reg = _registry(gui, rebuild=True)
    overlay, shell = gui._embedded_action_shell("Command Palette", kind="info", width=760, height=520)
    query = tk.StringVar()
    entry = tk.Entry(shell, textvariable=query, bg="#07090b", fg=TEXT, insertbackground=CYAN, relief="flat", font=("Consolas", 10))
    entry.pack(fill="x", padx=16, pady=(14, 8), ipady=7)
    box = tk.Listbox(shell, bg="#0c1014", fg=TEXT, selectbackground="#21404a", selectforeground=TEXT, bd=0, highlightthickness=1, highlightbackground=BORDER, font=("Consolas", 9), activestyle="none")
    box.pack(fill="both", expand=True, padx=16, pady=(0, 10))
    visible: list[ForgeCommandSpec] = []

    def refill(*_args: Any) -> None:
        needle = query.get().strip().casefold()
        visible.clear(); box.delete(0, "end")
        for row in reg.all():
            hay = f"{row.command_id} {row.label} {row.category} {row.description}".casefold()
            if needle and needle not in hay:
                continue
            visible.append(row)
            box.insert("end", f"{row.category}  ·  {row.label}    [{row.command_id}]")
        if visible:
            box.selection_set(0); box.activate(0)

    def run_selected() -> None:
        sel = box.curselection()
        if not sel:
            return
        row = visible[int(sel[0])]
        gui._finish_embedded_action(overlay)
        gui.window.after(80, lambda: reg.invoke(row.command_id))

    query.trace_add("write", refill)
    box.bind("<Double-Button-1>", lambda _e: run_selected())
    box.bind("<Return>", lambda _e: run_selected())
    shell.bind("<Escape>", lambda _e: gui._finish_embedded_action(overlay))
    refill(); entry.focus_force()



def _safe_cli_argv(gui: Any, command: str, extra: Iterable[str] = ()) -> str:
    """Return a readable, lightly-redacted provider command line for the Project Console."""
    try:
        argv = [str(x) for x in gui.backend.argv(command, tuple(extra))] if gui.backend is not None else [command, *map(str, extra)]
    except Exception:
        argv = [command, *map(str, extra)]
    redacted: list[str] = []
    secret_next = False
    secret_flags = {"--token", "--password", "--secret", "--api-key", "--apikey", "--key"}
    for arg in argv:
        low = arg.casefold()
        if secret_next:
            redacted.append("***")
            secret_next = False
            continue
        if low in secret_flags:
            redacted.append(arg); secret_next = True; continue
        if any(low.startswith(prefix) for prefix in ("token=", "password=", "secret=", "api_key=", "apikey=")):
            redacted.append(arg.split("=", 1)[0] + "=***")
            continue
        redacted.append(arg)
    return subprocess.list2cmdline(redacted) if os.name == "nt" else shlex.join(redacted)


def _open_project_cli_console(gui: Any) -> None:
    """Project CLI is an integrated projection of the selected project's provider commands.

    ForgePY no longer needs a second foreground console window for normal project CLI
    use.  The same provider command registry that drives Operations and the palette is
    rendered into the persistent Project Console, and the existing console input is
    the command entry surface.
    """
    reg = _registry(gui, rebuild=True)
    provider = str(getattr(getattr(gui, "backend", None), "provider_label", "") or "project provider")
    root = Path(gui.root_path)
    lines = [
        "",
        f"=== PROJECT CLI · {getattr(gui.contract, 'name', root.name)} ===",
        f"Root     : {root}",
        f"Provider : {provider}",
        "Type a command below and press Enter/Run.  Use < to keep the command browser open.",
    ]
    for category in CATEGORY_ORDER:
        rows = [r for r in reg.all() if r.category == category and r.source != "forge"]
        if not rows:
            continue
        lines.append("")
        lines.append(category.upper())
        for row in rows:
            key = row.provider_key or row.command_id
            lines.append(f"  {key:<30} {row.label}")
    lines.append("")
    _log(gui, "\n".join(lines), "info")
    try:
        _refresh_console_catalog(gui)
        gui._console_show_suggestions(force_all=True)
        if hasattr(gui, "_forge_console_toggle"):
            gui._forge_console_toggle.configure(text="<")
        gui.console_command_entry.focus_set()
    except Exception:
        pass


def _console_heartbeat(gui: Any, run_id: int, command: str, started: float) -> None:
    if int(getattr(gui, "_forge_live_run_id", -1)) != int(run_id):
        return
    if not bool(getattr(gui, "_busy", False)):
        return
    last = float(getattr(gui, "_forge_last_child_output", started) or started)
    now = time.monotonic()
    silent_for = now - last
    if silent_for >= 1.5:
        _log(gui, f"[RUNNING] {command} is active; waiting for provider output ({silent_for:.1f}s since last child output).", "info")
    try:
        gui.window.after(2000, lambda: _console_heartbeat(gui, run_id, command, started))
    except Exception:
        pass


def _start_command_live(gui: Any, original: Callable[..., Any], command: str, extra: Iterable[str] = (), *, label: str | None = None) -> Any:
    """Start a project command with immediate transcript + heartbeat visibility."""
    run_id = int(getattr(gui, "_forge_live_run_id", 0) or 0) + 1
    gui._forge_live_run_id = run_id
    started = time.monotonic()
    gui._forge_last_child_output = started
    shown = str(label or command)
    _log(gui, f"[CLI] {getattr(gui.contract, 'name', Path(gui.root_path).name)} · {shown}", "info")
    _log(gui, f"[CLI] {_safe_cli_argv(gui, command, extra)}", "muted")
    result = original(gui, command, tuple(extra), label=label)
    try:
        if bool(getattr(gui, "_busy", False)):
            gui.window.after(1400, lambda: _console_heartbeat(gui, run_id, shown, started))
    except Exception:
        pass
    return result


def _install_live_console_policy(gui: Any) -> None:
    """Prefer line-immediate GUI delivery instead of the old 64-line/32-KiB batching."""
    try:
        from ForgePYSettings import set_section
        set_section("ui", {"consoleBatchLines": 1, "consoleBatchBytes": 4096})
    except Exception as exc:
        _log(gui, f"[WARN] Live console batching policy could not be persisted: {exc}", "warn")

def _build_operations(gui: Any, parent: Any) -> None:
    tk = gui.tk
    shell = tk.Frame(parent, bg=BG)
    shell.pack(fill="both", expand=True, padx=14, pady=12)
    gui._section_title(shell, "Operations", "Project-owned commands and certified tools, normalized into stable ForgePY categories. Common Full Gate / Build / Run stay on the Quick Bar.")
    body = tk.PanedWindow(shell, orient="horizontal", bg=BG, bd=0, sashwidth=5, sashrelief="flat")
    body.pack(fill="both", expand=True)
    nav = gui._panel(body, "Categories")
    content = gui._panel(body, "Project Operations")
    body.add(nav, minsize=180, width=205, stretch="never")
    body.add(content, minsize=520, stretch="always")
    gui._forge_operations_nav = nav
    gui._forge_operations_content = content
    _refresh_operations(gui)


def _refresh_operations(gui: Any) -> None:
    nav = getattr(gui, "_forge_operations_nav", None)
    content = getattr(gui, "_forge_operations_content", None)
    if nav is None or content is None:
        return
    for host in (nav, content):
        for child in list(host.winfo_children()):
            child.destroy()
    groups = _registry(gui, rebuild=True).operation_groups()
    tk = gui.tk
    if not groups:
        tk.Label(content, text="No project-specific certified operations are declared yet.\n\nCommon Full Gate / Build / Run remain available from the Quick Bar.", bg=PANEL, fg=MUTED, font=("Segoe UI", 10), justify="left", anchor="nw").pack(fill="both", expand=True, padx=16, pady=16)
        return
    selected = {"name": next(iter(groups))}
    buttons: dict[str, Any] = {}

    def show(category: str) -> None:
        selected["name"] = category
        for key, btn in buttons.items():
            btn.configure(fg=CYAN if key == category else TEXT, bg=PANEL_2 if key == category else PANEL)
        for child in list(content.winfo_children()):
            child.destroy()
        tk.Label(content, text=category.upper(), bg=PANEL, fg=CYAN, font=("Segoe UI Semibold", 10), anchor="w").pack(fill="x", padx=12, pady=(8, 6))
        canvas = tk.Canvas(content, bg=PANEL, bd=0, highlightthickness=0)
        scroll = gui.ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=PANEL)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8)); scroll.pack(side="right", fill="y", pady=(0, 8), padx=(0, 6))
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        for row in groups[category]:
            card = tk.Frame(inner, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER)
            card.pack(fill="x", padx=4, pady=4)
            txt = tk.Frame(card, bg=PANEL_2); txt.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            tk.Label(txt, text=row.label, bg=PANEL_2, fg=TEXT, font=("Segoe UI Semibold", 9), anchor="w").pack(fill="x")
            desc = row.description or row.command_id
            tk.Label(txt, text=desc, bg=PANEL_2, fg=MUTED, font=("Segoe UI", 8), anchor="w", justify="left", wraplength=520).pack(fill="x", pady=(2, 0))
            tk.Label(card, text=row.risk.upper(), bg=PANEL_2, fg=YELLOW if row.risk != "read-only" else MUTED, font=("Consolas", 7)).pack(side="left", padx=8)
            gui._button(card, "Run", lambda cid=row.command_id: _registry(gui).invoke(cid), compact=True, primary=(row.risk == "read-only")).pack(side="right", padx=10, pady=8)

    for category in groups:
        btn = tk.Button(nav, text=category, command=lambda c=category: show(c), bg=PANEL, fg=TEXT, activebackground=PANEL_2, activeforeground=CYAN, bd=0, relief="flat", cursor="hand2", font=("Segoe UI", 9), anchor="w", padx=12, pady=7)
        btn.pack(fill="x", padx=5, pady=1); buttons[category] = btn
    gui._button(nav, "Command Palette", lambda: _open_command_palette(gui), compact=True).pack(fill="x", padx=7, pady=(12, 5))
    show(selected["name"])


def _policy_state(item: dict[str, Any], all_items: list[dict[str, Any]]) -> tuple[str, str]:
    state = str(item.get("state") or "").upper()
    manifest = item.get("manifest") if isinstance(item.get("manifest"), dict) else {}
    patch_id = str(item.get("patch_id") or manifest.get("patchId") or "")
    requires = [str(x) for x in (manifest.get("requires") or []) if str(x).strip()]
    supersedes = [str(x) for x in (manifest.get("supersedes") or []) if str(x).strip()]
    conflicts = [str(x) for x in (manifest.get("conflictsWith") or manifest.get("conflicts_with") or []) if str(x).strip()]
    states = {str(x.get("patch_id") or ""): str(x.get("state") or "").upper() for x in all_items}
    missing = [req for req in requires if states.get(req) not in {"APPLIED", "LINEAGE", "ARCHIVED"}]
    if missing:
        return "NEEDS ATTENTION", "Requires: " + ", ".join(missing)
    active_conflicts = [
        patch for patch in conflicts
        if states.get(patch) in {"AVAILABLE", "READY", "QUEUED", "STAGED", "APPLIED"}
    ]
    if active_conflicts:
        return "NEEDS ATTENTION", "Conflicts with: " + ", ".join(active_conflicts)
    superseded_by = []
    for other in all_items:
        other_manifest = other.get("manifest") if isinstance(other.get("manifest"), dict) else {}
        if patch_id and patch_id in [str(x) for x in (other_manifest.get("supersedes") or [])]:
            superseded_by.append(str(other.get("patch_id") or other.get("source_name") or "newer patch"))
    if superseded_by and state not in {"APPLIED", "LINEAGE", "ARCHIVED"}:
        return "HISTORY", "Superseded by " + ", ".join(superseded_by)
    if state in {"AVAILABLE", "READY"}:
        return "READY", "Compatible; approval required"
    if state in {"QUEUED", "STAGED"}:
        return "READY", "Approved; resume Apply + Full Gate"
    if state in {"REVIEW", "CANDIDATE"}:
        return "NEEDS ATTENTION", str(item.get("error") or item.get("classification") or "Approval/review required")
    if state in {"APPLIED", "LINEAGE", "ARCHIVED", "IGNORED", "SUPERSEDED", "ROLLED_BACK", "FAILED", "QUARANTINED"}:
        return "HISTORY", str(item.get("error") or item.get("classification") or state)
    return "NEEDS ATTENTION", str(item.get("error") or item.get("classification") or state or "Unknown state")


def _load_update_rows(gui: Any) -> dict[str, list[dict[str, Any]]]:
    try:
        from ForgePYIntake import list_items
        all_items = list(list_items() or [])
    except Exception:
        all_items = []
    relevant = [item for item in all_items if _item_belongs(gui, item)]
    buckets = {"Ready": [], "Needs Attention": [], "History": []}
    for item in relevant:
        bucket, reason = _policy_state(item, all_items)
        copy = dict(item); copy["_forge_reason"] = reason
        if bucket == "READY": buckets["Ready"].append(copy)
        elif bucket == "HISTORY": buckets["History"].append(copy)
        else: buckets["Needs Attention"].append(copy)
    return buckets


def _build_updates(gui: Any, parent: Any) -> None:
    tk = gui.tk
    shell = tk.Frame(parent, bg=BG)
    shell.pack(fill="both", expand=True, padx=14, pady=12)
    gui._section_title(shell, "Updates", "One governed intake workflow. Discovery never executes code; approved patches apply transactionally and certify through the target project's Full Gate.")
    top = tk.Frame(shell, bg=BG); top.pack(fill="x", pady=(0, 8))
    gui._button(top, "Check for updates", lambda: _show_updates(gui, run_scan=True), primary=True, compact=True).pack(side="left", padx=(0, 5))
    gui._button(top, "Apply Patch…", lambda: _choose_patch(gui), compact=True).pack(side="left", padx=5)
    tk.Label(top, text="Drop .patch / update on the Health folder icon", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="right")
    tabs = tk.Frame(shell, bg=BG); tabs.pack(fill="x", pady=(0, 7))
    host = gui._panel(shell); host.pack(fill="both", expand=True)
    gui._forge_updates_host = host
    gui._forge_updates_mode = "Ready"
    gui._forge_update_tab_buttons = {}
    for name in ("Ready", "Needs Attention", "History"):
        btn = gui._button(tabs, name, lambda n=name: _set_update_mode(gui, n), compact=True, primary=(name == "Ready"))
        btn.pack(side="left", padx=(0, 5)); gui._forge_update_tab_buttons[name] = btn
    _refresh_updates_workspace(gui)


def _choose_patch(gui: Any) -> None:
    selected = gui.filedialog.askopenfilename(
        parent=gui.window, title="Select ForgePY patch/update",
        filetypes=(("Forge patch transports", "*.patch *.zip"), ("Patch files", "*.patch"), ("All files", "*.*")),
    )
    if selected:
        try:
            gui._forge_ingest_patch(Path(selected))
        except Exception as exc:
            gui._popup("Updates", str(exc), kind="error")


def _set_update_mode(gui: Any, mode: str) -> None:
    gui._forge_updates_mode = mode
    for name, btn in getattr(gui, "_forge_update_tab_buttons", {}).items():
        try:
            btn.configure(fg=CYAN if name == mode else TEXT)
        except Exception:
            pass
    _refresh_updates_workspace(gui)


def _scan_updates_async(gui: Any) -> None:
    if getattr(gui, "_forge_f440_update_scan", False):
        return
    gui._forge_f440_update_scan = True
    _log(gui, "[INFO] Checking Downloads and configured intake roots for updates.")
    def work() -> None:
        error = ""
        try:
            from ForgePYIntake import scan_downloads, scan_roots
            from ForgePYPaths import intake_roots
            scan_downloads(force_stable=False, remove_source=True)
            roots = tuple(intake_roots())
            if roots:
                scan_roots(roots, force_stable=False, remove_source=True, trusted_roots=roots)
        except Exception as exc:
            error = str(exc)
        def done() -> None:
            gui._forge_f440_update_scan = False
            if error:
                _log(gui, f"[WARN] Update scan completed with warning: {error}", "warn")
            _refresh_updates_workspace(gui)
        _dispatch(gui, done)
    threading.Thread(target=work, daemon=True, name="ForgeF440UpdateScan").start()


def _show_updates(gui: Any, *, run_scan: bool = False) -> None:
    try:
        gui._show_app_tab("Updates")
    except Exception:
        pass
    if run_scan:
        _scan_updates_async(gui)
    else:
        _refresh_updates_workspace(gui)


def _refresh_updates_workspace(gui: Any) -> None:
    host = getattr(gui, "_forge_updates_host", None)
    buckets = _load_update_rows(gui)
    ready = buckets.get("Ready", [])
    button = getattr(gui, "_forge_quick_update_button", None)
    if button is not None:
        try:
            if ready and not button.winfo_manager():
                button.pack(side="left", padx=4)
            elif not ready and button.winfo_manager():
                button.pack_forget()
        except Exception:
            pass
    if host is None:
        return
    for child in list(host.winfo_children()):
        child.destroy()
    mode = str(getattr(gui, "_forge_updates_mode", "Ready") or "Ready")
    rows = buckets.get(mode, [])
    tk = gui.tk
    if not rows:
        tk.Label(host, text=f"No {mode.lower()} updates for {gui.contract.name}.", bg=PANEL, fg=MUTED, font=("Segoe UI", 10), anchor="nw").pack(fill="both", expand=True, padx=14, pady=14)
        return
    tree_frame = tk.Frame(host, bg=PANEL); tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 6))
    tree = gui.ttk.Treeview(tree_frame, columns=("state", "reason", "received"), show="tree headings", selectmode="browse")
    tree.heading("#0", text="Patch"); tree.column("#0", width=300, anchor="w")
    for key, title, width in (("state", "State", 110), ("reason", "Status", 330), ("received", "Received", 150)):
        tree.heading(key, text=title); tree.column(key, width=width, anchor="w")
    scrollbar = gui.ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview); tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
    mapping: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(rows):
        iid = f"update-{idx}"; mapping[iid] = item
        tree.insert("", "end", iid=iid, text=str(item.get("patch_id") or item.get("source_name") or "patch"), values=(str(item.get("state") or ""), str(item.get("_forge_reason") or ""), str(item.get("received_utc") or "")[:19].replace("T", " ")))
    if rows:
        first = tree.get_children()[0]; tree.selection_set(first); tree.focus(first)
    gui._forge_updates_tree = tree; gui._forge_updates_map = mapping
    actions = tk.Frame(host, bg=PANEL); actions.pack(fill="x", padx=10, pady=(0, 10))
    if mode == "Ready":
        gui._button(actions, "Apply + Full Gate", lambda: _apply_selected_ready(gui), primary=True, compact=True).pack(side="left", padx=(0, 5))
    elif mode == "Needs Attention":
        gui._button(actions, "Approve", lambda: _approve_selected_review(gui, False), primary=True, compact=True).pack(side="left", padx=(0, 5))
        gui._button(actions, "Approve + Apply + Full Gate", lambda: _approve_selected_review(gui, True), compact=True).pack(side="left", padx=5)
        gui._button(actions, "Route…", lambda: _route_selected_review(gui), compact=True).pack(side="left", padx=5)
    gui._button(actions, "Details", lambda: _show_update_details(gui), compact=True).pack(side="left", padx=5)
    gui._button(actions, "Reveal", lambda: _reveal_selected_update(gui), compact=True).pack(side="left", padx=5)
    gui._button(actions, "Refresh", lambda: _refresh_updates_workspace(gui), compact=True).pack(side="right")


def _selected_update(gui: Any) -> dict[str, Any] | None:
    tree = getattr(gui, "_forge_updates_tree", None)
    if tree is None:
        return None
    sel = tree.selection()
    return getattr(gui, "_forge_updates_map", {}).get(sel[0]) if sel else None


def _update_target_root(gui: Any, item: dict[str, Any]) -> Path | None:
    """Resolve the durable patch target without trusting the currently selected workspace."""
    for raw in (
        item.get("resolvedRoot"),
        item.get("approved_root"),
        (item.get("buildVerification") or {}).get("resolvedRoot") if isinstance(item.get("buildVerification"), dict) else None,
        ((item.get("buildVerification") or {}).get("identity") or {}).get("root") if isinstance(item.get("buildVerification"), dict) else None,
    ):
        value = str(raw or "").strip()
        if not value:
            continue
        try:
            root = Path(value).expanduser().resolve()
        except Exception:
            continue
        if root.exists():
            return root
    target = str(item.get("target_project") or "").strip()
    if target:
        try:
            root = gui._registry_root_for_patch_target(target)
            if root is not None:
                return Path(root).expanduser().resolve()
        except Exception:
            pass
    if _item_belongs(gui, item):
        return Path(gui.root_path).expanduser().resolve()
    return None


def _update_transport(item: dict[str, Any]) -> Path | None:
    for key in ("vault_path", "original_path"):
        raw = str(item.get(key) or "").strip()
        if not raw:
            continue
        try:
            path = Path(raw).expanduser().resolve()
        except Exception:
            continue
        if path.is_file():
            return path
    return None


def _preflight_update_item(gui: Any, item: dict[str, Any]) -> tuple[Path | None, str]:
    root = _update_target_root(gui, item)
    if root is None:
        return None, "No registered target root can be proven for this patch."
    transport = _update_transport(item)
    if transport is None:
        # The intake catalog may have already promoted the immutable transport into a
        # transaction-owned location.  Do not invent a failure when the catalog itself
        # still has a durable approved queue row; the patch engine will revalidate it.
        if str(item.get("state") or "").upper() in {"QUEUED", "STAGED"}:
            return root, "Approved queue transport is managed by ForgePY intake."
        return None, "The immutable patch transport cannot be found in Vault/intake storage."
    try:
        from VaultPatchEngine import validate_transport
        checked = validate_transport(transport, root)
        files = list(checked.get("files") or [])
        digest = str(checked.get("sha256") or item.get("sha256") or "")
        return root, f"PASS · {len(files)} file(s) · {digest[:12]}"
    except Exception as exc:
        return None, f"Preflight failed: {exc}"


def _update_details_text(gui: Any, item: dict[str, Any]) -> str:
    manifest = item.get("manifest") if isinstance(item.get("manifest"), dict) else {}
    verification = item.get("buildVerification") if isinstance(item.get("buildVerification"), dict) else {}
    root = _update_target_root(gui, item)
    transport = _update_transport(item)
    mismatches = list(verification.get("mismatches") or [])
    lines = [
        f"Patch ID       : {item.get('patch_id') or manifest.get('patchId') or '-'}",
        f"State          : {item.get('state') or '-'}",
        f"Classification : {item.get('classification') or '-'}",
        f"Target project : {item.get('target_project') or manifest.get('project') or '-'}",
        f"Target root    : {root or '-'}",
        f"Transport      : {transport or item.get('vault_path') or item.get('original_path') or '-'}",
        f"SHA-256        : {item.get('sha256') or '-'}",
        f"Received UTC   : {item.get('received_utc') or '-'}",
        f"Schema         : {manifest.get('schema') or '-'}",
        f"Engine         : {manifest.get('engine') or manifest.get('transportFormat') or '-'}",
        f"Verification   : {verification.get('status') or '-'}",
    ]
    for key, label in (("requires", "Requires"), ("supersedes", "Supersedes"), ("conflictsWith", "Conflicts")):
        values = [str(x) for x in (manifest.get(key) or []) if str(x).strip()]
        if values:
            lines.append(f"{label:<15}: {', '.join(values)}")
    if mismatches:
        lines.append("")
        lines.append("MISMATCHES")
        for row in mismatches:
            if isinstance(row, dict):
                lines.append(f"  {row.get('field') or '?'}: expected={row.get('expected')} actual={row.get('actual')}")
            else:
                lines.append(f"  {row}")
    reason = str(item.get("_forge_reason") or item.get("error") or "").strip()
    if reason:
        lines += ["", "STATUS", f"  {reason}"]
    return "\n".join(lines)


def _show_update_details(gui: Any) -> None:
    item = _selected_update(gui)
    if not item:
        return
    try:
        overlay, shell = gui._embedded_action_shell("Update Details", kind="info", width=780, height=560)
    except Exception:
        gui._popup("Update Details", _update_details_text(gui, item), kind="info")
        return
    tk = gui.tk
    actions = tk.Frame(shell, bg=PANEL); actions.pack(side="bottom", fill="x", padx=14, pady=(8, 14))
    gui._button(actions, "Close", lambda: gui._finish_embedded_action(overlay), primary=True, compact=True).pack(side="right")
    text = tk.Text(shell, bg="#07090b", fg=TEXT, insertbackground=CYAN, bd=0, relief="flat", font=("Consolas", 9), wrap="word")
    sy = gui.ttk.Scrollbar(shell, orient="vertical", command=text.yview); text.configure(yscrollcommand=sy.set)
    text.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(6, 0)); sy.pack(side="right", fill="y", padx=(0, 14), pady=(6, 0))
    text.insert("1.0", _update_details_text(gui, item)); text.configure(state="disabled")


def _apply_first_ready(gui: Any) -> None:
    rows = _load_update_rows(gui).get("Ready", [])
    if not rows:
        _show_updates(gui, run_scan=True)
        return
    _apply_ready_item(gui, rows[0])


def _apply_selected_ready(gui: Any) -> None:
    item = _selected_update(gui)
    if item:
        _apply_ready_item(gui, item)


def _apply_ready_item(gui: Any, item: dict[str, Any]) -> None:
    state = str(item.get("state") or "").upper()
    name = str(item.get("patch_id") or item.get("source_name") or "Update")
    root, preflight = _preflight_update_item(gui, item)
    if root is None:
        _log(gui, f"[FAIL] Patch preflight rejected {name}: {preflight}", "fail")
        gui._popup("Patch Preflight", f"{name}\n\n{preflight}\n\nNothing was applied.", kind="error")
        return
    _log(gui, f"[PATCH] {name} · target={root} · state={state} · {preflight}", "info")
    if state in {"QUEUED", "STAGED"}:
        if not gui._popup("Apply + Full Gate", f"{name}\n\nTarget: {root}\n{preflight}\n\nThis update is already approved. Resume transactional apply and run the authoritative Full Gate?", kind="warning", confirm=True):
            return
        try:
            gui._start_universal_project_apply(root, "apply-updates", run_full_after=True)
        except Exception as exc:
            gui._popup("Updates", str(exc), kind="error")
        return
    # AVAILABLE/READY: use the existing hash/source-binding approval authority after
    # an explicit transport + target preflight.  Approval still revalidates inside the
    # canonical intake engine, so this is additive defense rather than a bypass.
    try:
        import ForgeSimplifiedUX as ux
        ux._apply_cataloged_and_gate(gui, item)
    except Exception as exc:
        gui._popup("Updates", str(exc), kind="error")


def _approve_selected_review(gui: Any, apply_now: bool) -> None:
    item = _selected_update(gui)
    if not item:
        return
    target = str(item.get("target_project") or "")
    try:
        root = gui._registry_root_for_patch_target(target)
    except Exception:
        root = None
    if root is None:
        gui._popup("Updates", f"No registered project matches '{target}'. Route the patch first.", kind="warning")
        return
    try:
        from ForgePYIntake import reevaluate_review_item
        approved = reevaluate_review_item(str(item.get("intake_id") or ""), root)
    except Exception as exc:
        gui._popup("Updates", f"Approval could not complete:\n{exc}", kind="warning")
        _refresh_updates_workspace(gui); return
    _log(gui, f"[PASS] Approved {approved.get('patch_id') or approved.get('source_name')} for {root}.", "pass")
    _refresh_updates_workspace(gui)
    if apply_now:
        gui.window.after(120, lambda: gui._start_universal_project_apply(root, "apply-updates", run_full_after=True))


def _route_selected_review(gui: Any) -> None:
    item = _selected_update(gui)
    if not item:
        return
    initial = str(item.get("target_project") or getattr(gui.contract, "project_id", ""))
    target = gui._ask_text("Route Patch", "Registered project ID / alias:", initial=initial)
    if not target:
        return
    try:
        from ForgePYIntake import retarget_review_item
        retarget_review_item(str(item.get("intake_id") or ""), target.strip())
        _log(gui, f"[PASS] Routed patch to {target.strip()}; explicit approval is still required.", "pass")
    except Exception as exc:
        gui._popup("Updates", str(exc), kind="error")
    _refresh_updates_workspace(gui)


def _reveal_selected_update(gui: Any) -> None:
    item = _selected_update(gui)
    if not item:
        return
    path = Path(str(item.get("vault_path") or ""))
    if not path.exists():
        return
    try:
        from PCCSurfaceCommon import reveal_file
        reveal_file(path)
    except Exception:
        pass


def _source_status_text(root: Path) -> str:
    try:
        from ForgePYSourceControl import status
        st = status(root)
    except Exception:
        st = {}
    return (
        f"Branch : {st.get('branch') or '-'}\n"
        f"HEAD   : {st.get('headShort') or '-'}\n"
        f"Tree   : {'CLEAN' if st.get('clean') else 'DIRTY'}\n"
        f"Remote : {'GitHub configured' if st.get('githubConfigured') else 'Local only'}"
    )


def _build_source_control(gui: Any, parent: Any) -> None:
    tk = gui.tk
    shell = tk.Frame(parent, bg=BG); shell.pack(fill="both", expand=True, padx=14, pady=12)
    gui._section_title(shell, "Source Control", "Local Source owns branch/recovery history. GitHub is the remote backup/publish surface and GREEN publication target.")
    tabs = tk.Frame(shell, bg=BG); tabs.pack(fill="x", pady=(0, 8))
    host = tk.Frame(shell, bg=BG); host.pack(fill="both", expand=True)
    pages = {name: tk.Frame(host, bg=BG) for name in ("Local Source", "GitHub")}
    buttons: dict[str, Any] = {}
    def show(name: str) -> None:
        for p in pages.values(): p.pack_forget()
        pages[name].pack(fill="both", expand=True)
        for n, b in buttons.items():
            try: b.configure(fg=CYAN if n == name else TEXT)
            except Exception: pass
        if name == "Local Source": _refresh_local_source(gui)
        else: _refresh_github(gui)
    for name in pages:
        btn = gui._button(tabs, name, lambda n=name: show(n), compact=True, primary=(name == "Local Source"))
        btn.pack(side="left", padx=(0, 5)); buttons[name] = btn
    _build_local_source(gui, pages["Local Source"])
    _build_github(gui, pages["GitHub"])
    show("Local Source")


def _build_local_source(gui: Any, parent: Any) -> None:
    tk = gui.tk
    panes = tk.PanedWindow(parent, orient="horizontal", bg=BG, bd=0, sashwidth=5, sashrelief="flat")
    panes.pack(fill="both", expand=True)
    left = gui._panel(panes, "Branches / History")
    right = gui._panel(panes, "Recovery Diff")
    panes.add(left, minsize=320, width=390, stretch="never"); panes.add(right, minsize=480, stretch="always")
    tools = tk.Frame(left, bg=PANEL); tools.pack(fill="x", padx=8, pady=(0, 6))
    gui._button(tools, "+ Branch", lambda: _create_branch(gui), primary=True, compact=True).pack(side="left", padx=(0, 4))
    gui._button(tools, "Switch", lambda: _switch_branch(gui), compact=True).pack(side="left", padx=4)
    gui._button(tools, "Backup", lambda: _backup_source(gui), compact=True).pack(side="left", padx=4)
    gui._button(tools, "Restore", lambda: _restore_source(gui), compact=True).pack(side="left", padx=4)
    gui._button(tools, "Milestone", lambda: _create_milestone(gui), compact=True).pack(side="left", padx=4)
    tree = gui.ttk.Treeview(left, columns=("sha", "kind"), show="tree headings", selectmode="browse")
    tree.heading("#0", text="Branch / Ref"); tree.column("#0", width=210, anchor="w")
    tree.heading("sha", text="SHA"); tree.column("sha", width=95, anchor="w")
    tree.heading("kind", text="Kind"); tree.column("kind", width=90, anchor="w")
    sc = gui.ttk.Scrollbar(left, orient="vertical", command=tree.yview); tree.configure(yscrollcommand=sc.set)
    tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8)); sc.pack(side="right", fill="y", padx=(0, 6), pady=(0, 8))
    gui._forge_local_tree = tree
    tree.bind("<<TreeviewSelect>>", lambda _e: _refresh_recovery_diff(gui))
    header = tk.Label(right, text="", bg=PANEL, fg=CYAN, font=("Segoe UI Semibold", 9), anchor="w")
    header.pack(fill="x", padx=10, pady=(0, 6)); gui._forge_recovery_header = header
    text = tk.Text(right, bg="#07090b", fg=TEXT, insertbackground=CYAN, bd=0, relief="flat", font=("Consolas", 8), wrap="none")
    sy = gui.ttk.Scrollbar(right, orient="vertical", command=text.yview); sx = gui.ttk.Scrollbar(right, orient="horizontal", command=text.xview)
    text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8)); sy.pack(side="right", fill="y", padx=(0, 6), pady=(0, 8)); sx.pack(side="bottom", fill="x")
    gui._forge_recovery_diff = text


def _branch_rows(root: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in _git_lines(root, "for-each-ref", "--format=%(refname:short)|%(objectname:short)", "refs/heads"):
        if "|" in line:
            name, sha = line.rsplit("|", 1); rows.append((name, sha, "branch"))
    for line in _git_lines(root, "for-each-ref", "--format=%(refname)|%(objectname:short)", "refs/forgepy/recovery"):
        if "|" in line:
            ref, sha = line.rsplit("|", 1); name = ref.removeprefix("refs/forgepy/recovery/"); rows.append((f"Recovery/{name}", sha, "recovery"))
    for line in _git_lines(root, "tag", "--list", "forgepy-milestone/*", "--format=%(refname:short)|%(objectname:short)"):
        if "|" in line:
            name, sha = line.rsplit("|", 1); rows.append((name, sha, "milestone"))
    return rows


def _refresh_local_source(gui: Any) -> None:
    tree = getattr(gui, "_forge_local_tree", None)
    if tree is None: return
    root = Path(gui.root_path)
    ensure_recovery_ref(root)
    tree.delete(*tree.get_children())
    current = _branch(root)
    for idx, (name, sha, kind) in enumerate(_branch_rows(root)):
        iid = f"ref-{idx}"; tree.insert("", "end", iid=iid, text=("● " if name == current else "") + name, values=(sha, kind))
    if tree.get_children():
        tree.selection_set(tree.get_children()[0])
    _refresh_recovery_diff(gui)


def _refresh_recovery_diff(gui: Any) -> None:
    text = getattr(gui, "_forge_recovery_diff", None)
    header = getattr(gui, "_forge_recovery_header", None)
    if text is None: return
    root = Path(gui.root_path); branch = _branch(root); ref = recovery_ref(root, branch); rec = recovery_sha(root, branch)
    head = _git(root, "rev-parse", "--short", "HEAD", timeout=15).stdout.strip()
    if header is not None: header.configure(text=f"{branch}  ↔  Recovery/{_safe_ref_component(branch)}    HEAD {head or '-'}    RECOVERY {rec[:12] if rec else '-'}")
    if rec:
        cp = _git(root, "diff", "--stat", ref, "HEAD", timeout=30)
        detail = _git(root, "diff", "--name-status", ref, "HEAD", timeout=30)
        value = (cp.stdout or "No committed changes since recovery.\n") + "\n" + (detail.stdout or "")
    else:
        value = "No recovery ref exists yet. It will be created from the current HEAD and advanced only after certified GREEN checkpoints."
    text.configure(state="normal"); text.delete("1.0", "end"); text.insert("1.0", value); text.configure(state="disabled")


def _create_branch(gui: Any) -> None:
    root = Path(gui.root_path); current = _branch(root)
    name = gui._ask_text("Create Branch", "New branch name:", initial="feature/")
    if not name: return
    cp = _git(root, "switch", "-c", name.strip(), current, timeout=30)
    _log(gui, cp.stdout, "pass" if cp.returncode == 0 else "fail")
    if cp.returncode == 0:
        ensure_recovery_ref(root, name.strip()); _refresh_local_source(gui); _refresh_status(gui)
    else: gui._popup("Source Control", cp.stdout or "Branch creation failed.", kind="error")


def _switch_branch(gui: Any) -> None:
    names = [name for name, _sha, kind in _branch_rows(Path(gui.root_path)) if kind == "branch"]
    value = gui._ask_text("Switch Branch", "Branch name:", initial=_branch(Path(gui.root_path)))
    if not value: return
    if value.strip() not in names:
        gui._popup("Source Control", f"Unknown local branch: {value.strip()}", kind="warning"); return
    cp = _git(Path(gui.root_path), "switch", value.strip(), timeout=30)
    _log(gui, cp.stdout, "pass" if cp.returncode == 0 else "fail")
    if cp.returncode == 0:
        ensure_recovery_ref(Path(gui.root_path), value.strip()); _refresh_local_source(gui); _refresh_status(gui)


def _backup_source(gui: Any) -> None:
    try:
        import ForgeSimplifiedUX as ux
        ux._backup_local(gui)
    except Exception as exc:
        gui._popup("Source Control", str(exc), kind="error")


def _restore_source(gui: Any) -> None:
    root = Path(gui.root_path); branch = _branch(root); ref = recovery_ref(root, branch)
    rec = recovery_sha(root, branch)
    if not rec:
        gui._popup("Restore Source", "No certified recovery ref exists for this branch yet.", kind="warning"); return
    if not gui._popup("Restore Source", f"Restore working source to Recovery/{branch}\n{rec[:12]}?\n\nUncommitted changes will be discarded only after this explicit confirmation.", kind="warning", confirm=True):
        return
    cp = _git(root, "reset", "--hard", ref, timeout=60)
    _log(gui, cp.stdout, "pass" if cp.returncode == 0 else "fail")
    if cp.returncode == 0:
        _refresh_local_source(gui); _refresh_status(gui)
    else: gui._popup("Restore Source", cp.stdout or "Restore failed.", kind="error")


def _create_milestone(gui: Any) -> None:
    root = Path(gui.root_path)
    name = gui._ask_text("Create Milestone", "Milestone name:", initial=datetime.now().strftime("milestone-%Y%m%d"))
    if not name: return
    safe = _safe_ref_component(name).replace("/", "-")
    tag = f"forgepy-milestone/{safe}"
    cp = _git(root, "tag", "-a", tag, "-m", f"ForgePY certified milestone {name}", timeout=30)
    if cp.returncode != 0:
        gui._popup("Milestone", cp.stdout or "Could not create milestone tag.", kind="error"); return
    receipt = {
        "schema": "forgepy.milestone.v1",
        "name": name,
        "tag": tag,
        "project": str(getattr(gui.contract, "project_id", root.name)),
        "branch": _branch(root),
        "head": _git(root, "rev-parse", "HEAD", timeout=15).stdout.strip(),
        "createdUtc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        from ForgePYPaths import artifact_central_root
        dest = artifact_central_root() / "projects" / str(getattr(gui.contract, "project_id", root.name)).casefold() / "milestones"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{safe}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        _log(gui, f"[WARN] Milestone tag created but Vault receipt failed: {exc}", "warn")
    gui._popup("Milestone", f"Created {tag} at {receipt['head'][:12]}.", kind="success"); _refresh_local_source(gui)


def _build_github(gui: Any, parent: Any) -> None:
    tk = gui.tk
    summary = tk.Label(parent, text="", bg=PANEL_2, fg=TEXT, font=("Consolas", 9), justify="left", anchor="nw", padx=12, pady=10)
    summary.pack(fill="x", pady=(0, 8)); gui._forge_github_summary = summary
    actions = tk.Frame(parent, bg=BG); actions.pack(fill="x", pady=(0, 8))
    try:
        import ForgeSimplifiedUX as ux
        backup = lambda: ux._backup_github(gui); restore = lambda: ux._restore_github(gui)
    except Exception:
        backup = lambda: None; restore = lambda: None
    gui._button(actions, "Backup", backup, primary=True, compact=True).pack(side="left", padx=(0, 5))
    gui._button(actions, "Restore", restore, compact=True).pack(side="left", padx=5)
    gui._button(actions, "Fetch", lambda: _github_fetch(gui), compact=True).pack(side="left", padx=5)
    gui._button(actions, "Compare", lambda: _github_compare(gui), compact=True).pack(side="left", padx=5)
    gui._button(actions, "Refresh", lambda: _refresh_github(gui), compact=True).pack(side="right")
    output = tk.Text(parent, bg="#07090b", fg=TEXT, bd=0, relief="flat", font=("Consolas", 8), wrap="none", height=16)
    output.pack(fill="both", expand=True); gui._forge_github_output = output


def _refresh_github(gui: Any) -> None:
    label = getattr(gui, "_forge_github_summary", None)
    if label is None: return
    root = Path(gui.root_path)
    try:
        from ForgePYSourceControl import status
        st = status(root)
    except Exception:
        st = {}
    sync = "IN SYNC" if st.get("githubConfigured") and st.get("ahead") in {0, None} and st.get("behind") in {0, None} else "ATTENTION"
    label.configure(text=(f"Repository : {st.get('githubDeclaredUrl') or 'Configured GitHub remote'}\nBranch     : {st.get('branch') or '-'}\nLocal      : {st.get('headShort') or '-'}\nStatus     : {sync}\nAhead/Back : {st.get('ahead')} / {st.get('behind')}\nAutomatic GREEN publish: ON"), fg=GREEN if sync == "IN SYNC" else YELLOW)


def _github_fetch(gui: Any) -> None:
    cp = _git(Path(gui.root_path), "fetch", "--all", "--prune", timeout=180)
    _log(gui, cp.stdout, "pass" if cp.returncode == 0 else "fail"); _refresh_github(gui)


def _github_compare(gui: Any) -> None:
    root = Path(gui.root_path); cp = _git(root, "rev-parse", "--abbrev-ref", "@{upstream}", timeout=15)
    if cp.returncode != 0:
        gui._popup("GitHub Compare", "No upstream branch is configured.", kind="warning"); return
    upstream = cp.stdout.strip(); diff = _git(root, "diff", "--stat", f"HEAD...{upstream}", timeout=30)
    text = getattr(gui, "_forge_github_output", None)
    if text is not None:
        text.configure(state="normal"); text.delete("1.0", "end"); text.insert("1.0", diff.stdout or "No differences."); text.configure(state="disabled")


def _build_ide(gui: Any, parent: Any) -> None:
    """Native authoritative IDE surface; no Monaco/pywebview competing lane."""
    tk, ttk = gui.tk, gui.ttk
    shell = tk.Frame(parent, bg=BG); shell.pack(fill="both", expand=True, padx=12, pady=10)
    gui._section_title(shell, "ForgePY IDE", "Native project-aware editing, search, Git state, diffs and problems. External language servers can be added through project adapters without a parallel web IDE.")
    toolbar = tk.Frame(shell, bg=BG); toolbar.pack(fill="x", pady=(0, 7))
    gui._button(toolbar, "Refresh Files", lambda: _ide_refresh(gui), primary=True, compact=True).pack(side="left", padx=(0, 5))
    gui._button(toolbar, "Save", lambda: _ide_save_current(gui), compact=True).pack(side="left", padx=5)
    gui._button(toolbar, "Save All", lambda: _ide_save_all(gui), compact=True).pack(side="left", padx=5)
    gui._button(toolbar, "Find", lambda: _ide_find(gui), compact=True).pack(side="left", padx=5)
    gui._button(toolbar, "Search Project", lambda: _ide_project_search(gui), compact=True).pack(side="left", padx=5)
    gui._button(toolbar, "Diff HEAD", lambda: _ide_diff_current(gui), compact=True).pack(side="left", padx=5)
    gui._button(toolbar, "Command Palette", lambda: _open_command_palette(gui), compact=True).pack(side="right")
    gui.ide_status_label = tk.Label(toolbar, text="Native IDE ready", bg=BG, fg=GREEN, font=("Segoe UI", 8)); gui.ide_status_label.pack(side="right", padx=8)

    outer = tk.PanedWindow(shell, orient="horizontal", bg=BG, sashwidth=5, bd=0); outer.pack(fill="both", expand=True)
    left = gui._panel(outer, "Project Files"); work = tk.Frame(outer, bg=BG); outer.add(left, minsize=250, width=300); outer.add(work, minsize=600, stretch="always")
    gui.ide_tree = ttk.Treeview(left, columns=("git",), show="tree headings", selectmode="browse")
    gui.ide_tree.heading("#0", text="File"); gui.ide_tree.column("#0", width=230, anchor="w")
    gui.ide_tree.heading("git", text="Git"); gui.ide_tree.column("git", width=45, anchor="center")
    sy = ttk.Scrollbar(left, orient="vertical", command=gui.ide_tree.yview); gui.ide_tree.configure(yscrollcommand=sy.set)
    gui.ide_tree.pack(side="left", fill="both", expand=True, padx=(7, 0), pady=7); sy.pack(side="right", fill="y", padx=(0, 5), pady=7)
    gui.ide_tree.bind("<Double-1>", lambda _e: _ide_open_selected(gui)); gui.ide_tree.bind("<Return>", lambda _e: _ide_open_selected(gui))
    gui._ide_paths = {}

    vertical = tk.PanedWindow(work, orient="vertical", bg=BG, sashwidth=5, bd=0); vertical.pack(fill="both", expand=True)
    editor_host = gui._panel(vertical, "Editor"); bottom = gui._panel(vertical, "Problems / Search / Diff")
    vertical.add(editor_host, minsize=340, stretch="always"); vertical.add(bottom, minsize=130, height=190)
    tabs = ttk.Notebook(editor_host); tabs.pack(fill="both", expand=True, padx=7, pady=7); gui._forge_ide_tabs = tabs
    gui._forge_ide_editors = {}; gui._forge_ide_meta = {}
    tabs.bind("<<NotebookTabChanged>>", lambda _e: _ide_tab_changed(gui))
    gui.window.bind("<Control-s>", lambda _e: (_ide_save_current(gui), "break")[1], add="+")
    gui.window.bind("<Control-Shift-S>", lambda _e: (_ide_save_all(gui), "break")[1], add="+")
    gui.window.bind("<Control-Shift-P>", lambda _e: (_open_command_palette(gui), "break")[1], add="+")

    lower = ttk.Notebook(bottom); lower.pack(fill="both", expand=True, padx=7, pady=7); gui._forge_ide_lower = lower
    for name in ("Problems", "Search", "Diff"):
        frame = tk.Frame(lower, bg="#07090b"); lower.add(frame, text=name); setattr(gui, f"_forge_ide_{name.lower()}_frame", frame)
    problems = tk.Listbox(gui._forge_ide_problems_frame, bg="#07090b", fg=TEXT, selectbackground="#21404a", bd=0, highlightthickness=0, font=("Consolas", 8)); problems.pack(fill="both", expand=True); gui._forge_ide_problems = problems
    search = tk.Listbox(gui._forge_ide_search_frame, bg="#07090b", fg=TEXT, selectbackground="#21404a", bd=0, highlightthickness=0, font=("Consolas", 8)); search.pack(fill="both", expand=True); gui._forge_ide_search_results = search; gui._forge_ide_search_map = []
    search.bind("<Double-1>", lambda _e: _ide_open_search_result(gui))
    diff = tk.Text(gui._forge_ide_diff_frame, bg="#07090b", fg=TEXT, bd=0, relief="flat", font=("Consolas", 8), wrap="none"); diff.pack(fill="both", expand=True); gui._forge_ide_diff = diff
    _ide_refresh(gui)


def _ide_git_status(root: Path) -> dict[str, str]:
    cp = _git(root, "status", "--porcelain=v1", "--untracked-files=all", timeout=30)
    out: dict[str, str] = {}
    if cp.returncode != 0: return out
    for line in cp.stdout.splitlines():
        if len(line) < 4: continue
        code, path = line[:2].strip() or "M", line[3:].strip().replace("\\", "/")
        if " -> " in path: path = path.split(" -> ", 1)[1]
        out[path] = code
    return out


def _ide_refresh(gui: Any) -> None:
    if not hasattr(gui, "ide_tree"): return
    gui.ide_tree.delete(*gui.ide_tree.get_children()); gui._ide_paths.clear()
    try:
        from VaultIde import list_files
        files = list(list_files(Path(gui.root_path)) or [])
    except Exception as exc:
        gui.ide_status_label.configure(text=f"File scan failed: {exc}", fg=RED); return
    git = _ide_git_status(Path(gui.root_path))
    root_iid = "ide-root"; gui.ide_tree.insert("", "end", iid=root_iid, text=gui.contract.name, values=("",), open=True); gui._ide_paths[root_iid] = ""
    nodes = {"": root_iid}
    for rel in files:
        rel = str(rel).replace("\\", "/"); parts = Path(rel).parts; parent_key = ""; parent_iid = root_iid
        for part in parts[:-1]:
            key = "/".join([x for x in (parent_key, part) if x])
            if key not in nodes:
                iid = f"d{len(nodes)}"; gui.ide_tree.insert(parent_iid, "end", iid=iid, text=part, values=("",), open=False); nodes[key] = iid; gui._ide_paths[iid] = ""
            parent_iid = nodes[key]; parent_key = key
        iid = f"f{len(gui._ide_paths)}"; gui.ide_tree.insert(parent_iid, "end", iid=iid, text=parts[-1], values=(git.get(rel, ""),)); gui._ide_paths[iid] = rel
    gui.ide_status_label.configure(text=f"{len(files)} editable files · native IDE", fg=GREEN)


def _ide_open_selected(gui: Any) -> None:
    sel = gui.ide_tree.selection()
    if not sel: return
    rel = gui._ide_paths.get(sel[0], "")
    if rel: _ide_open_file(gui, rel)


def _ide_open_file(gui: Any, rel: str, line: int | None = None) -> None:
    if rel in gui._forge_ide_editors:
        frame = gui._forge_ide_editors[rel][0]; gui._forge_ide_tabs.select(frame)
        editor = gui._forge_ide_editors[rel][1]
    else:
        try:
            from VaultIde import read_file
            data = read_file(Path(gui.root_path), rel)
        except Exception as exc:
            gui._popup("ForgePY IDE", str(exc), kind="error"); return
        frame = gui.tk.Frame(gui._forge_ide_tabs, bg="#07090b")
        editor = gui.tk.Text(frame, bg="#090b0e", fg=TEXT, insertbackground=CYAN, selectbackground="#21404a", selectforeground=TEXT, bd=0, relief="flat", font=("Consolas", 10), undo=True, wrap="none")
        y = gui.ttk.Scrollbar(frame, orient="vertical", command=editor.yview); x = gui.ttk.Scrollbar(frame, orient="horizontal", command=editor.xview); editor.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        editor.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew"); frame.grid_rowconfigure(0, weight=1); frame.grid_columnconfigure(0, weight=1)
        editor.insert("1.0", str(data.get("text") or "")); editor.edit_modified(False)
        gui._forge_ide_tabs.add(frame, text=Path(rel).name); gui._forge_ide_editors[rel] = (frame, editor)
        gui._forge_ide_meta[rel] = {"encoding": data.get("encoding", "utf-8"), "newline": data.get("newline", "\n"), "dirty": False}
        def modified(_e: Any, path=rel, widget=editor) -> None:
            if not widget.edit_modified(): return
            widget.edit_modified(False); meta = gui._forge_ide_meta[path]
            if not meta.get("dirty"):
                meta["dirty"] = True; _ide_update_tab_title(gui, path)
        editor.bind("<<Modified>>", modified)
        gui._forge_ide_tabs.select(frame)
    if line:
        editor.mark_set("insert", f"{max(1, int(line))}.0"); editor.see("insert")
    gui._ide_current_path = rel; gui.ide_status_label.configure(text=rel, fg=TEXT)


def _ide_update_tab_title(gui: Any, rel: str) -> None:
    frame, _editor = gui._forge_ide_editors[rel]; dirty = bool(gui._forge_ide_meta.get(rel, {}).get("dirty")); gui._forge_ide_tabs.tab(frame, text=("*" if dirty else "") + Path(rel).name)


def _ide_tab_changed(gui: Any) -> None:
    selected = gui._forge_ide_tabs.select()
    for rel, (frame, _editor) in gui._forge_ide_editors.items():
        if str(frame) == str(selected): gui._ide_current_path = rel; gui.ide_status_label.configure(text=rel, fg=TEXT); break


def _ide_save_path(gui: Any, rel: str) -> bool:
    pair = gui._forge_ide_editors.get(rel)
    if not pair: return False
    _frame, editor = pair
    try:
        from VaultIde import write_file
        info = write_file(Path(gui.root_path), rel, editor.get("1.0", "end-1c"))
    except Exception as exc:
        gui._popup("ForgePY IDE", str(exc), kind="error"); return False
    gui._forge_ide_meta[rel]["dirty"] = False; _ide_update_tab_title(gui, rel); gui.ide_status_label.configure(text=f"Saved · {rel} · {info.get('bytes', 0)} bytes", fg=GREEN); return True


def _ide_save_current(gui: Any) -> None:
    rel = str(getattr(gui, "_ide_current_path", "") or "")
    if rel: _ide_save_path(gui, rel)


def _ide_save_all(gui: Any) -> None:
    count = 0
    for rel, meta in list(gui._forge_ide_meta.items()):
        if meta.get("dirty") and _ide_save_path(gui, rel): count += 1
    gui.ide_status_label.configure(text=f"Saved {count} dirty file(s).", fg=GREEN)


def _ide_find(gui: Any) -> None:
    rel = str(getattr(gui, "_ide_current_path", "") or ""); pair = gui._forge_ide_editors.get(rel)
    if not pair: return
    needle = gui._ask_text("Find", "Find text:", initial="")
    if not needle: return
    editor = pair[1]; pos = editor.search(needle, "insert+1c", stopindex="end") or editor.search(needle, "1.0", stopindex="end")
    if pos:
        end = f"{pos}+{len(needle)}c"; editor.tag_remove("sel", "1.0", "end"); editor.tag_add("sel", pos, end); editor.mark_set("insert", end); editor.see(pos)


def _ide_project_search(gui: Any) -> None:
    needle = gui._ask_text("Search Project", "Text or regular expression:", initial="")
    if not needle: return
    results = gui._forge_ide_search_results; results.delete(0, "end"); gui._forge_ide_search_map = []
    root = Path(gui.root_path); rg = shutil.which("rg")
    rows: list[tuple[str, int, str]] = []
    if rg:
        cp = subprocess.run([rg, "--line-number", "--no-heading", "--color", "never", needle, str(root)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", check=False, creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0)
        for line in cp.stdout.splitlines()[:1000]:
            m = re.match(r"^(.*?):(\d+):(.*)$", line)
            if m:
                try: rel = str(Path(m.group(1)).resolve().relative_to(root)).replace("\\", "/")
                except Exception: rel = m.group(1)
                rows.append((rel, int(m.group(2)), m.group(3).strip()))
    else:
        pattern = re.compile(needle)
        try:
            from VaultIde import list_files, read_file
            for rel in list_files(root):
                try: text = str(read_file(root, rel).get("text") or "")
                except Exception: continue
                for idx, line in enumerate(text.splitlines(), 1):
                    if pattern.search(line): rows.append((str(rel), idx, line.strip()))
                    if len(rows) >= 1000: break
                if len(rows) >= 1000: break
        except Exception: pass
    for rel, line_no, snippet in rows:
        gui._forge_ide_search_map.append((rel, line_no)); results.insert("end", f"{rel}:{line_no}  {snippet[:180]}")
    gui._forge_ide_lower.select(gui._forge_ide_search_frame)


def _ide_open_search_result(gui: Any) -> None:
    sel = gui._forge_ide_search_results.curselection()
    if not sel: return
    rel, line = gui._forge_ide_search_map[int(sel[0])]; _ide_open_file(gui, rel, line)


def _ide_diff_current(gui: Any) -> None:
    rel = str(getattr(gui, "_ide_current_path", "") or "")
    if not rel: return
    cp = _git(Path(gui.root_path), "diff", "--", rel, timeout=30)
    diff = gui._forge_ide_diff; diff.configure(state="normal"); diff.delete("1.0", "end"); diff.insert("1.0", cp.stdout or "No working-tree diff for this file."); diff.configure(state="disabled"); gui._forge_ide_lower.select(gui._forge_ide_diff_frame)


def _vault_rows() -> list[dict[str, Any]]:
    try:
        from VaultDriveIndex import list_entries
        return list(list_entries(limit=20000, offset=0) or [])
    except Exception:
        return []


def _vault_populate_rows(gui: Any, rows: list[dict[str, Any]], title: str) -> None:
    tree = getattr(gui, "vault_tree", None)
    if tree is None:
        return
    try:
        tree.delete(*tree.get_children()); gui._vault_node_paths.clear()
    except Exception:
        return
    root_iid = "vault-f440-filter"
    tree.insert("", "end", iid=root_iid, text=title, values=("FILTER", "", ""), open=True)
    for index, row in enumerate(rows[:5000]):
        path = Path(str(row.get("path") or ""))
        iid = f"vault-f440:{index}"
        cls = str(row.get("classification") or "UNKNOWN")
        size = int(row.get("bytes") or 0)
        modified = ""
        try:
            ns = int(row.get("mtime_ns") or 0)
            if ns: modified = datetime.fromtimestamp(ns / 1_000_000_000).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        try:
            human = gui._human_bytes(size)
        except Exception:
            human = str(size)
        tree.insert(root_iid, "end", iid=iid, text=path.name or str(path), values=(cls, human, modified), tags=(cls,))
        gui._vault_node_paths[iid] = path
    try:
        gui.vault_scan_status.configure(text=f"{title}: {len(rows)} item(s)", fg=CYAN)
    except Exception:
        pass


def _vault_filter(gui: Any, mode: str) -> None:
    rows = _vault_rows()
    mode_low = mode.casefold()
    if mode_low == "duplicates":
        by_hash: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            digest = str(row.get("sha256") or "").strip()
            if digest: by_hash.setdefault(digest, []).append(row)
        rows = [row for group in by_hash.values() if len(group) > 1 for row in group]
    elif mode_low in {"orphans", "unknown"}:
        rows = [row for row in rows if not str(row.get("owner_project_root") or "").strip() or str(row.get("classification") or "").upper() in {"UNKNOWN", "DIRECTORY"}]
    else:
        tokens = {
            "patches": ("PATCH",),
            "debug": ("DEBUG", "LOG"),
            "builds": ("BUILD", "BINARY", "GENERATED"),
            "releases": ("RELEASE", "PACKAGE", "INSTALLER"),
            "milestones": ("MILESTONE",),
            "backups": ("BACKUP", "RECOVERY", "SNAPSHOT"),
            "assets": ("ASSET",),
        }.get(mode_low, (mode.upper(),))
        filtered: list[dict[str, Any]] = []
        for row in rows:
            hay = f"{row.get('classification') or ''} {row.get('path') or ''} {row.get('name') or ''}".upper()
            if any(token in hay for token in tokens): filtered.append(row)
        rows = filtered
    _vault_populate_rows(gui, rows, mode.title())


def _vault_intelligence_bar(gui: Any, parent: Any) -> None:
    """Add evidence-centric Vault views without replacing the existing catalog browser."""
    tk = gui.tk
    shell_children = list(parent.winfo_children())
    if not shell_children:
        return
    shell = shell_children[0]
    children = list(shell.winfo_children())
    bar = tk.Frame(shell, bg=BG)
    if len(children) >= 2:
        try: bar.pack(fill="x", pady=(0, 7), after=children[1])
        except Exception: bar.pack(fill="x", pady=(0, 7))
    else:
        bar.pack(fill="x", pady=(0, 7))
    tk.Label(bar, text="Evidence:", bg=BG, fg=MUTED, font=("Segoe UI Semibold", 8)).pack(side="left", padx=(0, 5))
    for mode in ("Patches", "Debug", "Builds", "Releases", "Milestones", "Backups", "Assets", "Duplicates", "Orphans"):
        gui._button(bar, mode, lambda m=mode: _vault_filter(gui, m), compact=True).pack(side="left", padx=2)

def _top_nav_button(gui: Any, name: str, label: str, *, before: str = "Vault") -> None:
    if name in gui._app_tab_buttons: return
    tk = gui.tk
    target = gui._app_tab_buttons.get(before)
    btn = tk.Button(gui.app_nav_host, text=label, command=lambda n=name: gui._show_app_tab(n), bg=PANEL, fg=TEXT, activebackground=PANEL_2, activeforeground=CYAN, bd=0, relief="flat", cursor="hand2", font=("Segoe UI Semibold", 10), anchor="w", padx=20, pady=10)
    if target is not None:
        btn.pack(fill="x", padx=5, pady=1, before=target)
    else:
        btn.pack(fill="x", padx=5, pady=1)
    gui._app_tab_buttons[name] = btn


def _install_top_level_workspaces(gui: Any) -> None:
    if "Operations" not in gui._app_frames:
        frame = gui.tk.Frame(gui.app_content, bg=BG); gui._app_frames["Operations"] = frame; _build_operations(gui, frame); gui._built_app_tabs.add("Operations")
        _top_nav_button(gui, "Operations", "Operations", before="Vault")
    if "Updates" not in gui._app_frames:
        frame = gui.tk.Frame(gui.app_content, bg=BG); gui._app_frames["Updates"] = frame; _build_updates(gui, frame); gui._built_app_tabs.add("Updates")
        _top_nav_button(gui, "Updates", "Updates", before="Vault")
    # Project Workspace becomes Dashboard only. Remove its duplicate inner command rail.
    try:
        gui._app_tab_buttons["Project Workspace"].configure(text="Dashboard")
    except Exception:
        pass
    panes = getattr(gui, "workspace_panes", None)
    if panes is not None:
        try:
            pane_ids = list(panes.panes())
            if len(pane_ids) >= 2:
                first = gui.window.nametowidget(pane_ids[0]); panes.forget(first)
            gui._show_page("Dashboard")
        except Exception:
            pass
    tools = getattr(gui, "_forge_project_tool_host", None)
    if tools is not None:
        try: tools.pack_forget()
        except Exception: pass


def _set_left_rail(gui: Any, collapsed: bool) -> None:
    gui._app_rail_collapsed = bool(collapsed)
    width = 38 if collapsed else 158
    gui.app_nav_host.configure(width=width)
    gui.app_nav_title.configure(text="" if collapsed else "FORGEPY WORKSPACES")
    gui.app_nav_collapse.configure(text="›" if collapsed else "‹")
    display = {"Projects":"P", "Project Workspace":"D", "Operations":"O", "Updates":"U", "Vault":"V", "Source Control":"S", "IDE":"I", "Cortex":"C", "Settings":"⚙"}
    labels = {"Project Workspace":"Dashboard"}
    for key, btn in gui._app_tab_buttons.items():
        btn.configure(text=display.get(key, key[:1]) if collapsed else labels.get(key, key), anchor="center" if collapsed else "w", padx=5 if collapsed else 20)
    try:
        from ForgePYSettings import set_section
        set_section("ui", {"leftRailCollapsed": bool(collapsed)})
    except Exception:
        pass


def _refresh_status(gui: Any) -> None:
    root = Path(gui.root_path)
    try:
        from ForgePYSourceControl import status
        st = status(root)
    except Exception:
        st = {}
    try:
        from ForgePYIntake import counts_for_project
        # F415/F60R415 returns the legacy executable-queue contract as
        # (pending, invalid).  Newer provider/intake implementations may expose a
        # mapping instead.  Normalize both here so a status refresh can never take
        # down the GUI during startup/project activation.
        counts = counts_for_project(
            str(getattr(gui.contract, "project_id", root.name) or ""),
            str(getattr(gui.contract, "name", root.name) or ""),
            root.name,
        )
    except Exception:
        counts = (0, 0)
    project = str(getattr(gui.contract, "name", root.name))
    kind = str(getattr(gui.contract, "kind", "project") or "project")
    path = str(root)
    if len(path) > 42: path = "…" + path[-41:]
    branch = str(st.get("branch") or "-")
    clean = "CLEAN" if st.get("clean") else "DIRTY"
    sync = "SYNC" if st.get("githubConfigured") and st.get("ahead") in {0, None} and st.get("behind") in {0, None} else ("REMOTE" if st.get("githubConfigured") else "LOCAL")
    if isinstance(counts, dict):
        pending = int(counts.get("pending", 0) or 0)
        if not pending:
            pending = (
                int(counts.get("available", 0) or 0)
                + int(counts.get("queued", 0) or 0)
                + int(counts.get("review", 0) or 0)
            )
    elif isinstance(counts, (tuple, list)):
        # counts_for_project legacy contract: (pending, invalid)
        pending = int((counts[0] if counts else 0) or 0)
    else:
        try:
            pending = int(counts or 0)
        except Exception:
            pending = 0
    try: gui._forge_status_project.configure(text=f"{project} · {kind} · {path}")
    except Exception: pass
    try: gui._forge_status_git.configure(text=f"{branch} · {clean} · {sync} · Updates:{pending}")
    except Exception: pass
    try: gui._forge_quick_project.configure(text=project)
    except Exception: pass
    _refresh_updates_workspace(gui)


def _refresh_atomic(gui: Any) -> None:
    _registry(gui, rebuild=True)
    _refresh_status(gui)
    _refresh_operations(gui)
    _refresh_updates_workspace(gui)
    _refresh_local_source(gui)
    _refresh_github(gui)
    _ide_refresh(gui)


def _after_green_wrap(original: Callable[..., None], gui: Any, *args: Any, **kwargs: Any) -> None:
    # F415 performs the guarded certified commit/GitHub publish after GREEN.  Recovery
    # must advance to that newly committed revision, not to the pre-commit HEAD.
    original(gui, *args, **kwargs)
    root = Path(gui.root_path)
    attempts = {"left": 120}
    def wait_for_publish() -> None:
        attempts["left"] -= 1
        busy = bool(getattr(gui, "_busy", False) or getattr(gui, "_forge_auto_publish_running", False))
        if busy and attempts["left"] > 0:
            try: gui.window.after(500, wait_for_publish)
            except Exception: pass
            return
        ref = advance_recovery(root)
        if ref:
            _log(gui, f"[PASS] Local Source recovery advanced: {ref}", "pass")
        _refresh_status(gui)
    try: gui.window.after(500, wait_for_publish)
    except Exception: pass




def _preapply_snapshot(root: Path) -> dict[str, Any]:
    try:
        from ForgePYSourceControl import status
        st = dict(status(root) or {})
    except Exception:
        st = {}
    branch = str(st.get("branch") or _branch(root))
    ensure_recovery_ref(root, branch)
    return {
        "root": str(root),
        "branch": branch,
        "clean": bool(st.get("clean")),
        "head": str(st.get("head") or _git(root, "rev-parse", "HEAD", timeout=15).stdout.strip()),
        "recoveryRef": recovery_ref(root, branch),
        "recoverySha": recovery_sha(root, branch),
        "capturedUtc": datetime.now(timezone.utc).isoformat(),
    }


def _publish_green_target(gui: Any, root: Path) -> None:
    """Publish a GREEN target after Apply + Full Gate, including non-selected projects."""
    root = root.expanduser().resolve()
    def work() -> None:
        try:
            from PCCSurfaceCommon import ProjectContract
            from ForgeSourceControl import commit_push_green
            contract = ProjectContract.load(root)
            project_id = str(getattr(contract, "project_id", root.name))
            identity = {}
            try:
                from VaultBuildIdentity import build_identity
                identity = dict(build_identity(root) or {})
            except Exception:
                pass
            green = str(identity.get("greenId") or identity.get("projectBuild") or identity.get("projectVersion") or "GREEN")
            message = f"{getattr(contract, 'name', root.name)} GREEN {green} - certified by ForgePY Full Gate"
            cp = commit_push_green(root, project_id, message)
            ref = advance_recovery(root)
            def done() -> None:
                if cp.returncode == 0:
                    _log(gui, f"[PASS] Certified GREEN source published for {root.name}; recovery advanced to {ref or 'current HEAD'}.", "pass")
                else:
                    _log(gui, f"[WARN] GREEN source committed/recovery preserved, but remote publication needs attention:\n{cp.stdout}", "warn")
                _refresh_status(gui)
                _refresh_local_source(gui)
                _refresh_github(gui)
            _dispatch(gui, done)
        except Exception as exc:
            _dispatch(gui, lambda: _log(gui, f"[WARN] GREEN publication could not complete for {root}: {exc}", "warn"))
    threading.Thread(target=work, daemon=True, name="ForgeF440GreenPublish").start()


def _reveal_target_failure(gui: Any, root: Path) -> None:
    try:
        from PCCSurfaceCommon import latest_debug_bundle, reveal_file
        bundle = latest_debug_bundle(root)
        if bundle:
            reveal_file(Path(bundle)); return
    except Exception:
        pass
    _log(gui, f"[INFO] No debug bundle is currently available for {root}; failure details remain in Project Console.", "info")


def _rollback_failed_gate(gui: Any, root: Path, state: dict[str, Any], overlay: Any | None = None) -> None:
    if not bool(state.get("clean")) or not str(state.get("recoverySha") or ""):
        gui._popup("Roll Back Patch", "Automatic rollback is unavailable because the project was not clean before apply or no recovery revision exists. Keep the patched tree for repair or restore explicitly from Local Source.", kind="warning")
        return
    sha = str(state["recoverySha"])
    if not gui._popup("Roll Back Patch", f"Restore {root.name} to the pre-apply certified recovery revision {sha[:12]}?\n\nThe tree was clean before apply. Newly-created untracked files from this failed attempt will also be removed.", kind="warning", confirm=True):
        return
    cp = _git(root, "reset", "--hard", sha, timeout=60)
    clean = _git(root, "clean", "-fd", timeout=60) if cp.returncode == 0 else cp
    if cp.returncode == 0 and clean.returncode == 0:
        _log(gui, f"[PASS] Rolled back failed update for {root.name} to {sha[:12]}.", "pass")
        try:
            from ForgePYIntake import reconcile_project
            reconcile_project(root)
        except Exception:
            pass
        if overlay is not None:
            try: gui._finish_embedded_action(overlay)
            except Exception: pass
        _refresh_status(gui); _refresh_updates_workspace(gui); _refresh_local_source(gui)
    else:
        gui._popup("Roll Back Patch", (cp.stdout or clean.stdout or "Rollback failed."), kind="error")


def _offer_gate_failure_recovery(gui: Any, root: Path, error: str) -> None:
    state = dict(getattr(gui, "_forge_f440_preapply", {}).get(str(root.resolve()), {}) or {})
    tk = gui.tk
    try:
        overlay, shell = gui._embedded_action_shell("Full Gate Failed After Patch", kind="warning", width=760, height=390)
    except Exception:
        _log(gui, f"[FAIL] Patch applied but Full Gate failed for {root}: {error}", "fail")
        return
    tk.Label(shell, text="FULL GATE FAILED", bg=PANEL, fg=RED, font=("Segoe UI Semibold", 13), anchor="w").pack(fill="x", padx=16, pady=(12, 4))
    tk.Label(shell, text=f"The patch applied successfully to {root.name}. ForgePY preserved the patched source for diagnosis; it was not automatically rolled back.", bg=PANEL, fg=TEXT, font=("Segoe UI", 9), justify="left", anchor="w", wraplength=700).pack(fill="x", padx=16, pady=(0, 8))
    body = tk.Text(shell, bg="#07090b", fg=MUTED, bd=0, relief="flat", font=("Consolas", 8), wrap="word", height=9)
    body.pack(fill="both", expand=True, padx=16, pady=(0, 8)); body.insert("1.0", str(error)); body.configure(state="disabled")
    actions = tk.Frame(shell, bg=PANEL); actions.pack(fill="x", padx=16, pady=(0, 14))
    gui._button(actions, "View Failure", lambda: _reveal_target_failure(gui, root), primary=True, compact=True).pack(side="left", padx=(0, 5))
    rollback = gui._button(actions, "Roll Back Patch", lambda: _rollback_failed_gate(gui, root, state, overlay), compact=True, danger=True)
    rollback.pack(side="left", padx=5)
    if not bool(state.get("clean")) or not str(state.get("recoverySha") or ""):
        try: rollback.configure(state="disabled")
        except Exception: pass
    gui._button(actions, "Keep for Repair", lambda: gui._finish_embedded_action(overlay), compact=True).pack(side="right")



def _universal_apply_heartbeat(gui: Any, operation_id: int, target: Path, started: float) -> None:
    if int(getattr(gui, "_forge_universal_apply_id", -1)) != int(operation_id):
        return
    if not bool(getattr(gui, "_forge_universal_apply_active", False)):
        return
    last = float(getattr(gui, "_forge_last_child_output", started) or started)
    silent_for = time.monotonic() - last
    if silent_for >= 1.5:
        _log(gui, f"[RUNNING] Update transaction for {target.name} is active; waiting for patch/gate output ({silent_for:.1f}s).", "info")
    try:
        gui.window.after(2000, lambda: _universal_apply_heartbeat(gui, operation_id, target, started))
    except Exception:
        pass

class _F440EventProxy:
    def __init__(self, gui: Any, inner: Any) -> None:
        self.gui = gui
        self.inner = inner
    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)
    def put(self, item: Any, *args: Any, **kwargs: Any) -> Any:
        result = self.inner.put(item, *args, **kwargs)
        try:
            kind, payload = item
            if kind in {"log", "universal-build-log"}:
                self.gui._forge_last_child_output = time.monotonic()
            if kind == "universal-project-apply-done":
                self.gui._forge_universal_apply_active = False
                _label, target, run_full_after, info = payload
                gate = dict((info or {}).get("gate") or {})
                if bool(run_full_after) and gate.get("ran") and int(gate.get("returncode") or 0) == 0:
                    _dispatch(self.gui, lambda r=Path(target): _publish_green_target(self.gui, r))
                elif bool(run_full_after) and not gate.get("ran"):
                    _dispatch(self.gui, lambda r=Path(target): _log(self.gui, f"[FAIL] Patch transaction completed for {r.name}, but the requested Full Gate did not start.", "fail"))
                _dispatch(self.gui, lambda: _refresh_updates_workspace(self.gui))
            elif kind == "universal-project-apply-cancelled":
                self.gui._forge_universal_apply_active = False
                _dispatch(self.gui, lambda: _refresh_updates_workspace(self.gui))
            elif kind == "universal-project-apply-error":
                self.gui._forge_universal_apply_active = False
                _label, target, error = payload
                text = str(error or "")
                if "Patch applied, but target project certification failed" in text:
                    _dispatch(self.gui, lambda r=Path(target), e=text: _offer_gate_failure_recovery(self.gui, r, e))
                _dispatch(self.gui, lambda: _refresh_updates_workspace(self.gui))
        except Exception:
            pass
        return result

def _install_callback_registry_bridge() -> None:
    try:
        import ForgeSimplifiedUX as ux
    except Exception:
        return
    if getattr(ux, "_forge_f440_wrapped", False):
        return
    ux._forge_f440_wrapped = True
    original_green = ux._after_green
    def wrapped_after_green(gui: Any, *args: Any, **kwargs: Any) -> None:
        # F744: preserve the generation-aware completion contract added by the
        # simplified UX. Older one-argument wrappers caused GREEN publication
        # to crash after a successful gate.
        _after_green_wrap(original_green, gui, *args, **kwargs)
    ux._after_green = wrapped_after_green
    original_refresh = ux._refresh_compact_status
    ux._refresh_compact_status = lambda gui: (original_refresh(gui), _refresh_status(gui))


def install_normalization(cls: type[Any]) -> type[Any]:
    """Install the normalization layer on the already-patched GREEN F60R415 GUI class."""
    if getattr(cls, "_forge_f440_normalization_installed", False):
        return cls
    cls._forge_f440_normalization_installed = True
    previous_shell = cls._build_shell
    previous_activate = cls._activate_project
    previous_console_exec = cls._console_execute_entry
    previous_start_command = cls._start_command
    previous_build_vault = cls._build_vault_tab
    previous_universal_apply = cls._start_universal_project_apply

    cls._build_global_quick_actions = lambda self, parent: _quick_bar(self, parent)
    cls._build_global_statusbar = lambda self, parent: _status_bar(self, parent)
    cls._build_global_console = lambda self, parent: _console(self, parent)
    cls._build_source_control_tab = lambda self, parent: _build_source_control(self, parent)
    cls._build_ide_tab = lambda self, parent: _build_ide(self, parent)
    cls._refresh_console_command_catalog = lambda self: _refresh_console_catalog(self)
    cls._console_execute_entry = lambda self, event=None: _console_execute(self, previous_console_exec, event)
    cls._start_command = lambda self, command, extra=(), label=None: _start_command_live(self, previous_start_command, command, extra, label=label)
    cls._open_cli = lambda self: _open_project_cli_console(self)
    cls._set_app_rail_collapsed = lambda self, collapsed=False: _set_left_rail(self, collapsed)
    cls._toggle_app_rail = lambda self: _set_left_rail(self, not bool(getattr(self, "_app_rail_collapsed", False)))
    cls._forge_command_palette = lambda self: _open_command_palette(self)
    cls._forge_refresh_operations = lambda self: _refresh_operations(self)
    cls._forge_refresh_updates = lambda self: _refresh_updates_workspace(self)
    cls._forge_advance_recovery = lambda self: advance_recovery(Path(self.root_path))

    def start_universal_apply(self: Any, root: Path, *args: Any, **kwargs: Any) -> Any:
        target = Path(root).expanduser().resolve()
        snapshots = getattr(self, "_forge_f440_preapply", None)
        if snapshots is None:
            snapshots = {}; self._forge_f440_preapply = snapshots
        snapshots[str(target)] = _preapply_snapshot(target)
        operation_id = int(getattr(self, "_forge_universal_apply_id", 0) or 0) + 1
        self._forge_universal_apply_id = operation_id
        self._forge_universal_apply_active = True
        started = time.monotonic()
        self._forge_last_child_output = started
        _log(self, f"[INFO] Recovery snapshot recorded before patch apply: {snapshots[str(target)].get('recoveryRef')} @ {str(snapshots[str(target)].get('recoverySha') or '')[:12]}", "info")
        _log(self, f"[UPDATE] Apply + Full Gate started for {target}.", "info")
        result = previous_universal_apply(self, target, *args, **kwargs)
        try:
            self.window.after(1400, lambda: _universal_apply_heartbeat(self, operation_id, target, started))
        except Exception:
            pass
        return result
    cls._start_universal_project_apply = start_universal_apply

    def build_vault(self: Any, parent: Any) -> None:
        previous_build_vault(self, parent)
        # The F415 Vault already owns whole-drive catalog, lineage, Artifact Central,
        # unclassified content, portable storage and project association.  Keep that
        # robust workspace and simply brand the normalized evidence contract.
        try:
            first = parent.winfo_children()[0]
            banner = self.tk.Label(first, text="Vault Evidence Authority · projects / artifacts / patches / gates / logs / releases / milestones / recovery", bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w")
            children = first.winfo_children()
            if children:
                banner.pack(fill="x", pady=(0, 4), before=children[0])
            else:
                banner.pack(fill="x", pady=(0, 4))
        except Exception:
            pass
        try:
            _vault_intelligence_bar(self, parent)
        except Exception as exc:
            _log(self, f"[WARN] Vault evidence bar unavailable: {exc}", "warn")
    cls._build_vault_tab = build_vault

    def build_shell(self: Any) -> None:
        previous_shell(self)

        # F443: reclaim the legacy top ForgePY banner entirely.  Keep the widgets
        # alive for compatibility with old refresh code, but remove their geometry.
        # The selected-project identity now belongs to the bottom status bar and the
        # only permanent Project CLI control belongs to the Quick Bar.
        try:
            for child in list(self.window.winfo_children()):
                if child is getattr(self, "main_body", None):
                    break
                try:
                    child.pack_forget()
                except Exception:
                    pass
        except Exception:
            pass

        _install_top_level_workspaces(self)
        if not isinstance(getattr(self, "_event_q", None), _F440EventProxy):
            self._event_q = _F440EventProxy(self, self._event_q)
        _install_live_console_policy(self)
        _refresh_console_catalog(self)
        _refresh_status(self)
        self.window.bind("<Control-Shift-P>", lambda _e: (_open_command_palette(self), "break")[1], add="+")
        _log(self, f"[PASS] {NORMALIZATION_VERSION} ACTIVE.", "pass")
    cls._build_shell = build_shell

    def activate(self: Any, root: Path) -> None:
        previous_activate(self, root)
        _dispatch(self, lambda: _refresh_atomic(self))
    cls._activate_project = activate

    _install_callback_registry_bridge()
    return cls
