#!/usr/bin/env python3
"""Post-F60R390 simplified ForgePY operator workflow.

This module deliberately sits above the existing intake, patch, project-provider and
source-control authorities.  It does not replace validation.  It removes the need for
operators to drive validation plumbing manually.
"""
from __future__ import annotations

import ctypes
import os
import json
import queue
import re
import shutil
import subprocess
import threading
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

F60R415_UX_VERSION = "FORGEPY-SIMPLIFIED-UX-F60R415"
_PATCH_SUFFIXES = {".patch", ".zip"}


def _walk_widgets(widget: Any) -> Iterable[Any]:
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


def _find_button(gui: Any, text: str) -> Any | None:
    wanted = text.casefold().strip()
    for widget in _walk_widgets(gui.window):
        if _widget_text(widget).casefold().strip() == wanted:
            try:
                if widget.winfo_class() in {"Button", "TButton"}:
                    return widget
            except Exception:
                return widget
    return None


def _safe_log(gui: Any, message: str, tag: str = "info") -> None:
    try:
        gui._append_log(message.rstrip("\n") + "\n", tag)
    except Exception:
        pass


def _project_identity(root: Path) -> dict[str, Any]:
    try:
        from VaultBuildIdentity import build_identity
        return dict(build_identity(root) or {})
    except Exception:
        return {}


def _project_label(gui: Any) -> str:
    name = str(getattr(getattr(gui, "contract", None), "name", "") or gui.root_path.name)
    identity = _project_identity(Path(gui.root_path))
    build = str(identity.get("projectBuild") or identity.get("greenId") or identity.get("projectVersion") or "").strip()
    return f"{name}  ·  {build}" if build else name


def _source_status(root: Path) -> dict[str, Any]:
    try:
        from ForgePYSourceControl import status
        return dict(status(root) or {})
    except Exception:
        return {}


def _branch(root: Path) -> str:
    return str(_source_status(root).get("branch") or "")


def _latest_debug(root: Path) -> Path | None:
    try:
        from PCCSurfaceCommon import latest_debug_bundle
        value = latest_debug_bundle(root)
        if value:
            path = Path(value)
            return path if path.exists() else None
    except Exception:
        pass
    return None


def _reveal_file(path: Path) -> None:
    try:
        from PCCSurfaceCommon import reveal_file
        reveal_file(path)
        return
    except Exception:
        pass
    if os.name == "nt":
        subprocess.Popen(["explorer.exe", f"/select,{path}"], close_fds=True)
    else:
        subprocess.Popen(["xdg-open", str(path.parent)], close_fds=True)


def _refresh_compact_status(gui: Any) -> None:
    root = Path(gui.root_path)
    status = _source_status(root)
    branch = str(status.get("branch") or "-")
    clean = "CLEAN" if status.get("clean") else "DIRTY"
    remote = "SYNC" if status.get("githubConfigured") and status.get("ahead") in {None, 0} and status.get("behind") in {None, 0} else ("GITHUB" if status.get("githubConfigured") else "LOCAL")
    try:
        gui._forge_status_project.configure(text=_project_label(gui))
        gui._forge_status_git.configure(text=f"{branch} · {clean} · {remote}")
        if hasattr(gui, "_forge_quick_project"):
            gui._forge_quick_project.configure(text=_project_label(gui))
    except Exception:
        pass
    try:
        gui._forge_health_project.configure(text=str(getattr(gui.contract, "name", root.name)))
        identity = _project_identity(root)
        value = str(identity.get("projectBuild") or identity.get("projectVersion") or "No declared build")
        gui._forge_health_build.configure(text=value)
    except Exception:
        pass
    try:
        bundle = _latest_debug(root)
        gui._forge_debug_button.configure(state="normal" if bundle else "disabled")
    except Exception:
        pass


def _call_later(gui: Any, delay: int, func: Callable[[], None]) -> None:
    """Schedule from the Tk thread. Worker threads should use _dispatch_main()."""
    try:
        gui.window.after(delay, func)
    except Exception:
        pass


def _dispatch_main(gui: Any, func: Callable[[], None]) -> None:
    """Queue a GUI callback without calling Tk from a worker thread."""
    try:
        gui._forge_main_actions.put(func)
    except Exception:
        pass


def _drain_main_actions(gui: Any) -> None:
    actions = getattr(gui, "_forge_main_actions", None)
    if actions is None:
        return
    for _ in range(64):
        try:
            func = actions.get_nowait()
        except queue.Empty:
            break
        try:
            func()
        except Exception as exc:
            _safe_log(gui, f"[WARN] Deferred ForgePY GUI action failed: {exc}", "warn")


class _EventQueueProxy:
    """Observe process completion without replacing the existing GUI event contract."""

    def __init__(self, gui: Any, inner: Any) -> None:
        self.gui = gui
        self.inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def put(self, item: Any, *args: Any, **kwargs: Any) -> Any:
        result = self.inner.put(item, *args, **kwargs)
        try:
            kind, payload = item
            if kind == "done":
                command, rc = payload
                command = str(command or "")
                if command == "full":
                    generation = int(getattr(self.gui, "_forge_full_gate_generation", 0) or 0)
                    if int(rc) == 0:
                        self.gui._forge_full_gate_last_success_generation = generation
                        # Do not publish merely because the worker posted DONE. The base
                        # GUI must consume DONE first, render all preceding output and
                        # release its single-flight job slot.
                        _dispatch_main(
                            self.gui,
                            lambda generation=generation: _call_later(
                                self.gui, 50, lambda: _queue_green_publish_when_idle(self.gui, generation)
                            ),
                        )
                    else:
                        _dispatch_main(
                            self.gui,
                            lambda generation=generation: _call_later(
                                self.gui, 50, lambda: _queue_failure_debug_when_idle(self.gui, generation)
                            ),
                        )
                elif command in {"debug-bundle", "debug"} and int(rc) == 0:
                    if getattr(self.gui, "_forge_reveal_debug_after_generate", False):
                        self.gui._forge_reveal_debug_after_generate = False
                        _dispatch_main(self.gui, lambda: _call_later(self.gui, 250, lambda: _reveal_latest_debug(self.gui)))
                    else:
                        _dispatch_main(self.gui, lambda: _call_later(self.gui, 250, lambda: _refresh_compact_status(self.gui)))
                elif command == "apply-updates":
                    if getattr(self.gui, "_forge_gate_after_apply", False):
                        self.gui._forge_gate_after_apply = False
                        if int(rc) == 0:
                            _dispatch_main(self.gui, lambda: _call_later(self.gui, 300, lambda: self.gui._start_command("full")))
                        else:
                            _safe_log(self.gui, "[FAIL] Update application failed; Full Gate was not started.", "fail")
                elif command in {"commit-push-green", "auto-green-publish", "source-commit-push-green"}:
                    self.gui._forge_auto_publish_running = False
                    generation = int(getattr(self.gui, "_forge_green_publish_started_generation", 0) or 0)
                    self.gui._forge_green_publish_completed_generation = generation
                    _write_green_publication_receipt(self.gui, generation, int(rc), phase="completed" if int(rc) == 0 else "pending")
                    if int(rc) != 0:
                        _safe_log(self.gui, "[WARN] Project is GREEN, but GitHub publication is pending. Source was not force-pushed.", "warn")
                    _dispatch_main(self.gui, lambda: _call_later(self.gui, 250, lambda: _refresh_compact_status(self.gui)))
        except Exception:
            pass
        return result



def _write_green_publication_receipt(gui: Any, generation: int, returncode: int, *, phase: str) -> None:
    """Persist small runtime evidence for GREEN publication ordering.

    This lives under .forge/runtime and is intentionally outside governed source.
    It makes late GUI callbacks diagnosable without treating publication failure as
    a quality-gate failure.
    """
    try:
        root = Path(gui.root_path)
        target = root / ".forge" / "runtime" / "green-publication.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "forgepy.green-publication.v1",
            "generation": int(generation),
            "returncode": int(returncode),
            "phase": str(phase),
            "candidate": _project_identity(root).get("projectBuild") or "",
            "recordedUtc": datetime.now(timezone.utc).isoformat(),
        }
        temp = target.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, target)
    except Exception:
        pass


def _green_commit_message(gui: Any) -> str:
    root = Path(gui.root_path)
    identity = _project_identity(root)
    name = str(identity.get("projectName") or getattr(gui.contract, "name", root.name))
    green = str(identity.get("greenId") or identity.get("projectBuild") or identity.get("projectVersion") or "GREEN")
    return f"{name} GREEN {green} - certified by ForgePY Full Gate"


def _queue_green_publish_when_idle(gui: Any, generation: int, attempts: int = 160) -> None:
    """Publish only after the GUI has consumed Full Gate DONE and released the slot.

    The process worker can post DONE while the Tk event queue still contains a large
    backlog of console output. Scheduling publication directly from Queue.put() made
    publication race the GUI's DONE handler, which produced a misleading
    "Another ForgePY job is already running" popup on an otherwise GREEN gate.
    """
    current = int(getattr(gui, "_forge_full_gate_generation", 0) or 0)
    if generation != current:
        _safe_log(gui, f"[INFO] Ignored stale GREEN callback for Full Gate generation {generation}; current is {current}.", "info")
        return
    if int(getattr(gui, "_forge_full_gate_last_success_generation", -1) or -1) != generation:
        return
    active_proc = getattr(gui, "_active_proc", None)
    proc_running = bool(active_proc is not None and getattr(active_proc, "poll", lambda: 0)() is None)
    if bool(getattr(gui, "_busy", False)) or proc_running:
        if attempts > 0:
            _call_later(gui, 50, lambda: _queue_green_publish_when_idle(gui, generation, attempts - 1))
        else:
            _safe_log(gui, "[WARN] GREEN is certified but automatic publication remained queued because the operation slot never became idle.", "warn")
        return
    _after_green(gui, generation=generation)


def _after_green(gui: Any, *, generation: int | None = None) -> None:
    """Full Gate GREEN is the source-control publication boundary."""
    current = int(getattr(gui, "_forge_full_gate_generation", 0) or 0)
    if generation is not None and generation != current:
        _safe_log(gui, f"[INFO] Ignored stale GREEN callback for Full Gate generation {generation}; current is {current}.", "info")
        return
    if getattr(gui, "_forge_auto_publish_running", False):
        return
    if int(getattr(gui, "_forge_green_publish_completed_generation", -1) or -1) == current:
        return
    if int(getattr(gui, "_forge_green_publish_started_generation", -1) or -1) == current:
        return
    if bool(getattr(gui, "_busy", False)):
        # Defensive guard: normally _queue_green_publish_when_idle owns this path.
        _call_later(gui, 50, lambda: _queue_green_publish_when_idle(gui, current))
        return
    gui._forge_auto_publish_running = True
    gui._forge_green_publish_started_generation = current
    _write_green_publication_receipt(gui, current, 0, phase="starting")
    _safe_log(gui, "[PASS] Full Gate GREEN; automatically publishing the certified active branch.", "pass")
    try:
        project_id = str(getattr(gui.contract, "project_id", gui.root_path.name))
        gui._start_builtin_source(
            "commit-push-green",
            [project_id, _green_commit_message(gui)],
        )
        # _start_builtin_source historically returns None even for a guarded no-op.
        # Verify it actually acquired the slot so publication state cannot stick.
        if not bool(getattr(gui, "_busy", False)):
            gui._forge_auto_publish_running = False
            _safe_log(gui, "[WARN] GREEN is certified but automatic publication did not acquire the operation slot.", "warn")
            return
    except Exception as exc:
        gui._forge_auto_publish_running = False
        _safe_log(gui, f"[WARN] GREEN is certified but automatic GitHub publish could not start: {exc}", "warn")
        return

    def release_failsafe() -> None:
        if getattr(gui, "_forge_auto_publish_running", False) and not getattr(gui, "_busy", False):
            gui._forge_auto_publish_running = False
            _refresh_compact_status(gui)

    _call_later(gui, 30000, release_failsafe)


def _debug_provider_command(gui: Any) -> str:
    """Return a project debug-bundle command only when the provider actually exposes it."""
    backend = getattr(gui, "backend", None)
    if backend is None:
        return ""
    for key in ("debug-bundle", "debug.bundle", "debug"):
        try:
            if bool(backend.supports(key)):
                return key
        except Exception:
            continue
    return ""


def _fallback_debug_bundle(gui: Any, reason: str = "ForgePY diagnostic fallback") -> Path | None:
    """Create ForgePY-owned diagnostic evidence when no project debug command exists."""
    root = Path(gui.root_path).expanduser().resolve()
    try:
        out_dir = root / "artifacts" / "debug"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", str(getattr(gui.contract, "name", root.name) or root.name)).strip("-") or "Project"
        bundle = out_dir / f"{safe_name}_DebugBundle_{stamp}_FORGEPY_FALLBACK.zip"

        console_text = ""
        widget = getattr(gui, "console_text", None)
        if widget is not None:
            try:
                console_text = str(widget.get("1.0", "end-1c"))
            except Exception:
                console_text = ""
        if len(console_text) > 500_000:
            console_text = console_text[-500_000:]

        diagnostics = [
            f"reason={reason}",
            f"root={root}",
            f"project={getattr(gui.contract, 'name', root.name)}",
            f"kind={getattr(gui.contract, 'kind', '')}",
            f"timestamp={datetime.now().isoformat()}",
        ]
        try:
            cp = subprocess.run(
                [shutil.which("git") or "git", "-C", str(root), "status", "--short", "--branch"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", check=False, timeout=15,
                creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0,
            )
            diagnostics.extend(["", "[git status]", cp.stdout.rstrip()])
        except Exception as exc:
            diagnostics.extend(["", "[git status unavailable]", str(exc)])

        candidates: list[Path] = []
        for candidate in (
            root / "project.control.json",
            root / "logs" / "bootstrap" / "forgepy-bootstrap-latest.log",
        ):
            if candidate.is_file():
                candidates.append(candidate)
        sessions = root / "logs" / "sessions"
        if sessions.is_dir():
            try:
                latest = max((x for x in sessions.iterdir() if x.is_file()), key=lambda x: x.stat().st_mtime, default=None)
                if latest is not None:
                    candidates.append(latest)
            except Exception:
                pass

        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("FORGEPY_DIAGNOSTIC.txt", "\n".join(diagnostics).rstrip() + "\n")
            if console_text:
                zf.writestr("project-console.txt", console_text)
            for candidate in candidates:
                try:
                    rel = candidate.relative_to(root)
                    zf.write(candidate, str(rel).replace("\\", "/"))
                except Exception:
                    continue

        import hashlib
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        bundle.with_suffix(bundle.suffix + ".sha256").write_text(f"{digest}  {bundle.name}\n", encoding="utf-8")
        _safe_log(gui, f"[PASS] ForgePY fallback debug bundle created: {bundle}", "pass")
        return bundle
    except Exception as exc:
        _safe_log(gui, f"[WARN] ForgePY fallback debug bundle could not be created: {exc}", "warn")
        return None


def _queue_failure_debug_when_idle(gui: Any, generation: int, attempts: int = 160) -> None:
    """Create failure evidence only after the Full Gate DONE event is consumed."""
    current = int(getattr(gui, "_forge_full_gate_generation", 0) or 0)
    if generation != current:
        _safe_log(gui, f"[INFO] Ignored stale failed-gate diagnostic request for generation {generation}; current is {current}.", "info")
        return
    if int(getattr(gui, "_forge_full_gate_last_success_generation", -1) or -1) == generation:
        return
    active_proc = getattr(gui, "_active_proc", None)
    proc_running = bool(active_proc is not None and getattr(active_proc, "poll", lambda: 0)() is None)
    if bool(getattr(gui, "_busy", False)) or proc_running:
        if attempts > 0:
            _call_later(gui, 50, lambda: _queue_failure_debug_when_idle(gui, generation, attempts - 1))
        else:
            _safe_log(gui, "[WARN] Full Gate failed but the operation slot did not become idle; creating ForgePY fallback diagnostics.", "warn")
            _fallback_debug_bundle(gui, "Full Gate failed; operation slot remained busy while queueing diagnostics")
            _refresh_compact_status(gui)
        return
    _after_failure(gui, generation=generation)


def _after_failure(gui: Any, *, generation: int | None = None) -> None:
    current_generation = int(getattr(gui, "_forge_full_gate_generation", 0) or 0)
    if generation is not None and generation != current_generation:
        _safe_log(gui, f"[INFO] Ignored stale Full Gate failure callback for generation {generation}; current is {current_generation}.", "info")
        return
    if generation is not None and int(getattr(gui, "_forge_full_gate_last_success_generation", -1) or -1) == generation:
        return
    _safe_log(gui, "[INFO] Full Gate failed; ensuring one canonical debug handoff.", "info")
    current = _latest_debug(Path(gui.root_path))
    before = str(getattr(gui, "_forge_debug_before_full", "") or "")
    if current is not None and str(current) != before:
        _safe_log(gui, f"[PASS] Full Gate already produced the canonical debug bundle: {current}", "pass")
        _refresh_compact_status(gui)
        return

    command = _debug_provider_command(gui)
    if command:
        try:
            gui._forge_reveal_debug_after_generate = False
            gui._start_command(command, label=command)
            if bool(getattr(gui, "_busy", False)):
                return
            _safe_log(gui, f"[WARN] Project debug command {command!r} did not acquire the operation slot; using ForgePY fallback diagnostics.", "warn")
        except Exception as exc:
            _safe_log(gui, f"[WARN] Project debug command could not start: {exc}", "warn")

    _fallback_debug_bundle(gui, "Full Gate failed and no project debug-bundle command successfully started")
    _refresh_compact_status(gui)


def _reveal_latest_debug(gui: Any) -> None:
    bundle = _latest_debug(Path(gui.root_path))
    if bundle is None:
        _safe_log(gui, "[WARN] No current debug bundle is available to reveal.", "warn")
        return
    _safe_log(gui, f"[PASS] Revealing canonical debug bundle: {bundle}", "pass")
    _reveal_file(bundle)
    _refresh_compact_status(gui)


def _debug_clicked(gui: Any) -> None:
    bundle = _latest_debug(Path(gui.root_path))
    if bundle is not None:
        _reveal_file(bundle)
        return

    command = _debug_provider_command(gui)
    if command:
        try:
            gui._forge_reveal_debug_after_generate = True
            gui._start_command(command, label=command)
            if bool(getattr(gui, "_busy", False)):
                return
            _safe_log(gui, f"[WARN] Project debug command {command!r} did not acquire the operation slot; using ForgePY fallback diagnostics.", "warn")
        except Exception as exc:
            _safe_log(gui, f"[WARN] Project debug bundle could not be started: {exc}", "warn")

    bundle = _fallback_debug_bundle(gui, "DEBUG requested and project provider exposes no debug-bundle command")
    if bundle is not None:
        _reveal_file(bundle)
        _refresh_compact_status(gui)


def _check_updates(gui: Any) -> None:
    """One operator action: discover, classify and surface actionable updates."""
    if getattr(gui, "_forge_update_scan_running", False):
        return
    gui._forge_update_scan_running = True
    _safe_log(gui, "[INFO] Checking Downloads and configured intake roots for project updates.", "info")

    def worker() -> None:
        try:
            from ForgePYIntake import scan_downloads, scan_roots, available_globally, review_items
            from ForgePYPaths import intake_roots
            scan_downloads()
            roots = tuple(intake_roots())
            if roots:
                scan_roots(roots, force_stable=True, remove_source=True, trusted_roots=roots)
            ready = list(available_globally(compatible_only=True) or [])
            review = list(review_items() or [])
            gui._forge_update_scan_result = (ready, review, "")
        except Exception as exc:
            gui._forge_update_scan_result = ([], [], str(exc))

    threading.Thread(target=worker, daemon=True, name="ForgeSimpleUpdateScan").start()
    _call_later(gui, 800, lambda: _poll_simple_update_result(gui))


def _poll_simple_update_result(gui: Any) -> None:
    if not getattr(gui, "_forge_update_scan_running", False):
        return
    result = getattr(gui, "_forge_update_scan_result", None)
    if result is None:
        _call_later(gui, 300, lambda: _poll_simple_update_result(gui))
        return
    gui._forge_update_scan_result = None
    gui._forge_update_scan_running = False
    ready, review, error = result
    if error:
        gui._popup("Updates", f"Update scan failed:\n{error}", kind="error")
        return
    _present_updates(gui, list(ready), list(review))


def _present_updates(gui: Any, ready: list[dict[str, Any]], review: list[dict[str, Any]]) -> None:
    current = str(getattr(gui.contract, "project_id", "") or "").casefold()
    current_name = str(getattr(gui.contract, "name", "") or "").casefold()
    relevant = [
        item for item in ready
        if str(item.get("target_project") or "").casefold() in {current, current_name}
    ]
    if relevant:
        item = relevant[0]
        name = str(item.get("source_name") or item.get("patch_id") or "Update")
        if gui._popup(
            "Update Ready",
            f"{name}\n\nForgePY identified this as a compatible update for {gui.contract.name}.\n\nApply it and run the authoritative Full Gate?",
            kind="success",
            confirm=True,
        ):
            _apply_cataloged_and_gate(gui, item)
        return

    review_current = [
        item for item in review
        if str(item.get("target_project") or "").casefold() in {current, current_name}
    ]
    if review_current:
        # F415 temporarily hid the old Patch Review surface while simplifying menus, but
        # REVIEW is still a valid intake state and must retain an operator escape hatch.
        # Open the existing authoritative review surface directly instead of pointing at
        # a Project Operations page that no longer exists.
        open_review = gui._popup(
            "Update Needs Review",
            f"{len(review_current)} update(s) need review for {gui.contract.name}. "
            "ForgePY could not prove a safe unique apply path.\n\n"
            "Open Patch Review now?",
            kind="warning",
            confirm=True,
        )
        if open_review:
            try:
                gui._open_patch_review()
            except Exception as exc:
                _safe_log(gui, f"[WARN] Patch Review could not open: {exc}", "warn")
                gui._popup(
                    "Patch Review",
                    f"The review item was preserved, but the review surface could not open.\n\n{exc}",
                    kind="error",
                )
        return
    # A prior approval may already have promoted an item to QUEUED before a GUI/process
    # interruption. Surface that durable approval here instead of making the update
    # disappear from Check for Updates.
    try:
        from ForgePYIntake import list_items
        queued = [
            row for row in list(list_items() or [])
            if str(row.get("state") or "").upper() in {"QUEUED", "STAGED"}
            and str(row.get("target_project") or "").casefold() in {current, current_name}
        ]
    except Exception:
        queued = []
    if queued:
        name = str(queued[0].get("source_name") or queued[0].get("patch_id") or "Approved update")
        if gui._popup(
            "Approved Update Pending",
            f"{name}\n\nThis update is already approved and waiting in the guarded queue for {gui.contract.name}.\n\nResume Apply + Full Gate now?",
            kind="warning", confirm=True,
        ):
            gui._start_universal_project_apply(Path(gui.root_path), "apply-updates", run_full_after=True)
        return
    gui._popup("Updates", f"No actionable update is currently ready for {gui.contract.name}.", kind="info")


def _apply_cataloged_and_gate(gui: Any, item: dict[str, Any]) -> None:
    intake_id = str(item.get("intake_id") or "")
    if not intake_id:
        gui._popup("Update", "The update catalog entry has no intake identity.", kind="error")
        return

    gui._forge_simple_approval_result = None
    def worker() -> None:
        try:
            from ForgePYIntake import approve_available_globally
            approved = approve_available_globally(intake_id)
            gui._forge_simple_approval_result = (True, approved)
        except Exception as exc:
            gui._forge_simple_approval_result = (False, str(exc))

    threading.Thread(target=worker, daemon=True, name="ForgeSimpleApprove").start()
    _call_later(gui, 250, lambda: _wait_for_approval_then_apply(gui, 120))



def _wait_for_approval_then_apply(gui: Any, attempts: int, target_root: Path | None = None) -> None:
    result = getattr(gui, "_forge_simple_approval_result", None)
    if result is None:
        if attempts <= 0:
            gui._popup("Apply + Full Gate", "Timed out while approving the update. Nothing was applied.", kind="warning")
            return
        _call_later(gui, 250, lambda: _wait_for_approval_then_apply(gui, attempts - 1, target_root))
        return
    gui._forge_simple_approval_result = None
    ok, payload = result
    if not ok:
        gui._popup("Apply + Full Gate", f"Update approval failed:\n{payload}", kind="error")
        return
    _safe_log(gui, f"[PASS] Update approved for guarded queue: {payload}", "pass")
    # Use ForgePY's direct transactional universal lane for every normal project,
    # including the currently selected project. The old current-project path routed
    # back through `patch-apply`/ProcessHost and could appear to hang with no useful
    # progress even though the same canonical transport was already verified.
    resolved = target_root
    if resolved is None and isinstance(payload, dict):
        raw = str(payload.get("resolvedRoot") or payload.get("approved_root") or "").strip()
        if raw:
            resolved = Path(raw)
    if resolved is None:
        resolved = Path(gui.root_path)
    resolved = Path(resolved).expanduser().resolve()
    try:
        is_self = bool(gui._is_forgepy_root(resolved))
    except Exception:
        is_self = resolved == Path(gui.root_path).resolve() and bool(gui._is_forgepy_self_project())
    if is_self:
        gui._start_forgepy_self_apply("apply-updates", target_root=resolved)
        return
    if resolved != Path(gui.root_path).resolve():
        _safe_log(gui, f"[INFO] Applying queued patch to resolved project without changing the visible workspace: {resolved}", "info")
    gui._start_universal_project_apply(resolved, "apply-updates", run_full_after=True)

def _apply_queued_then_gate(gui: Any) -> None:
    """Apply the already-approved queue once, then chain directly into Full Gate.

    The operator has already approved the single simplified update card, so this path
    intentionally bypasses the legacy second confirmation while retaining the existing
    guarded patch engine and self-update authority.
    """
    try:
        gui._forge_gate_after_apply = True
        if bool(gui._is_forgepy_self_project()):
            # Self-update owns restart/recovery.  It cannot safely start another gate in
            # the dying GUI process; the restart path will show the new build ready for
            # its normal Full Gate.
            gui._forge_gate_after_apply = False
            gui._start_forgepy_self_apply("apply-updates")
            return
        gui._start_command("patch-apply", ["--yes"], label="apply-updates")
    except Exception as exc:
        gui._forge_gate_after_apply = False
        gui._popup("Apply + Full Gate", f"Update apply could not start:\n{exc}", kind="error")


def _ingest_patch(gui: Any, source: Path) -> None:
    source = Path(source).expanduser().resolve()
    if source.suffix.casefold() not in _PATCH_SUFFIXES or not source.is_file():
        gui._popup("Patch Intake", f"Unsupported update transport:\n{source.name}\n\nDrop a .patch or ForgePY patch package.", kind="warning")
        return
    _safe_log(gui, f"[INFO] Deep scanning dropped patch across registered projects: {source}", "info")

    def worker() -> None:
        try:
            from ForgePYIntake import resolve_patch_target
            resolution = dict(resolve_patch_target(source) or {})
            _dispatch_main(gui, lambda: _present_patch_resolution(gui, source, resolution))
        except Exception as exc:
            _dispatch_main(gui, lambda: gui._popup("Patch Intake", f"Patch scan failed:\n{exc}", kind="error"))

    threading.Thread(target=worker, daemon=True, name="ForgePatchDropResolve").start()


def _present_patch_resolution(gui: Any, source: Path, resolution: dict[str, Any]) -> None:
    status = str(resolution.get("status") or "").upper()
    if status == "RESOLVED":
        target_root = Path(str(resolution.get("targetRoot") or "")).expanduser().resolve()
        target_name = str(resolution.get("targetProject") or target_root.name)
        current = Path(gui.root_path).resolve()
        selected_hint = "" if current == target_root else f"\n\nCurrent project is {gui.contract.name}; ForgePY will safely switch this operation to {target_name}."
        if gui._popup(
            "Patch Ready",
            f"{source.name}\n\nTarget: {target_name}\nCompatibility: READY{selected_hint}\n\nApply this patch and run that project's authoritative Full Gate?",
            kind="success",
            confirm=True,
        ):
            _approve_manual_and_gate(gui, source, target_root)
        return
    if status == "AMBIGUOUS":
        matches = list(resolution.get("matches") or [])
        _choose_ambiguous_project(gui, source, matches)
        return
    reason = str(resolution.get("reason") or resolution.get("error") or "Patch does not currently apply to a registered project.")
    gui._popup("Patch Intake", f"{source.name}\n\n{reason}\n\nForgePY left the file untouched for review/lineage classification.", kind="warning")


def _registered_project_choices(gui: Any) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    try:
        entries = list(gui.registry.entries() or [])
    except Exception:
        entries = []
    for entry in entries:
        try:
            root = Path(entry.root).expanduser().resolve()
        except Exception:
            continue
        name = str(getattr(entry, "name", "") or root.name)
        rows.append((name, root))
    return rows


def _choose_ambiguous_project(gui: Any, source: Path, matches: list[dict[str, Any]]) -> None:
    candidates: list[tuple[str, Path]] = []
    for row in matches:
        raw = str(row.get("targetRoot") or row.get("root") or "").strip()
        if not raw:
            continue
        try:
            root = Path(raw).expanduser().resolve()
        except Exception:
            continue
        name = str(row.get("projectName") or row.get("targetProject") or row.get("projectId") or root.name)
        candidates.append((name, root))
    if not candidates:
        candidates = _registered_project_choices(gui)
    current = Path(gui.root_path).resolve()
    current_match = next(((name, root) for name, root in candidates if root == current), None)
    if current_match is not None:
        if gui._popup(
            "Patch Target Needs Confirmation",
            f"ForgePY found more than one plausible project for {source.name}.\n\n"
            f"Apply to the current project, {gui.contract.name}?\n\n"
            "ForgePY will deep-validate the patch against the project again before any file is changed.",
            kind="warning", confirm=True,
        ):
            _approve_manual_and_gate(gui, source, current)
            return
    names = [name for name, _ in candidates]
    hint = ", ".join(names[:10])
    chosen = gui._ask_text(
        "Choose Patch Project",
        f"Choose the project for {source.name}.\n\n"
        f"Registered candidates: {hint or 'none'}\n\n"
        "Type the project name exactly:",
        initial=names[0] if len(names) == 1 else "",
    )
    if not chosen or not chosen.strip():
        return
    key = chosen.strip().casefold()
    target = next((root for name, root in candidates if name.casefold() == key or root.name.casefold() == key), None)
    if target is None:
        target = next((root for name, root in _registered_project_choices(gui) if name.casefold() == key or root.name.casefold() == key), None)
    if target is None:
        gui._popup("Patch Intake", f"No registered project matches '{chosen.strip()}'. Nothing was applied.", kind="warning")
        return
    _approve_manual_and_gate(gui, source, target)


def _approve_manual_and_gate(gui: Any, source: Path, target_root: Path) -> None:
    # Patch routing follows the patch.  Applying to another registered project must
    # not switch the visible ForgePY workspace or silently change the selected Health rail.
    target_root = Path(target_root).expanduser().resolve()
    gui._forge_simple_approval_result = None
    def worker() -> None:
        try:
            from ForgePYIntake import approve_manual_patch_for_project
            approved = approve_manual_patch_for_project(target_root, source)
            gui._forge_simple_approval_result = (True, approved)
        except Exception as exc:
            gui._forge_simple_approval_result = (False, str(exc))

    threading.Thread(target=worker, daemon=True, name="ForgePatchDropApprove").start()
    _call_later(gui, 250, lambda: _wait_for_approval_then_apply(gui, 120, target_root))


def _choose_patch(gui: Any) -> None:
    selected = gui.filedialog.askopenfilename(
        parent=gui.window,
        title="Select ForgePY patch/update",
        filetypes=(("ForgePY patches", "*.patch *.zip"), ("Patch", "*.patch"), ("All files", "*.*")),
    )
    if selected:
        _ingest_patch(gui, Path(selected))


def _install_windows_drop(gui: Any) -> None:
    if os.name != "nt" or getattr(gui, "_forge_drop_installed", False):
        return
    try:
        gui.window.update_idletasks()
        hwnd = int(gui.window.winfo_id())
        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        WM_DROPFILES = 0x0233
        GWL_WNDPROC = -4
        from ctypes import wintypes
        LRESULT = ctypes.c_ssize_t
        WPARAM = wintypes.WPARAM
        LPARAM = wintypes.LPARAM
        HWND = wintypes.HWND
        UINT = wintypes.UINT
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

        get_long = user32.GetWindowLongPtrW
        set_long = user32.SetWindowLongPtrW
        call_proc = user32.CallWindowProcW

        # Win32 window procedures are pointer-sized.  Without explicit argtypes, ctypes
        # falls back to 32-bit c_int conversion for CallWindowProcW's first argument,
        # which truncates/overflows WNDPROC addresses on 64-bit Windows.
        get_long.argtypes = [HWND, ctypes.c_int]
        get_long.restype = ctypes.c_void_p
        set_long.argtypes = [HWND, ctypes.c_int, ctypes.c_void_p]
        set_long.restype = ctypes.c_void_p
        call_proc.argtypes = [ctypes.c_void_p, HWND, UINT, WPARAM, LPARAM]
        call_proc.restype = LRESULT

        shell32.DragAcceptFiles.argtypes = [HWND, wintypes.BOOL]
        shell32.DragAcceptFiles.restype = None
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, UINT, wintypes.LPWSTR, UINT]
        shell32.DragQueryFileW.restype = UINT
        shell32.DragFinish.argtypes = [wintypes.HANDLE]
        shell32.DragFinish.restype = None

        old_proc = get_long(HWND(hwnd), GWL_WNDPROC)
        if not old_proc:
            raise OSError("GetWindowLongPtrW(GWLP_WNDPROC) returned NULL")

        def wndproc(hWnd: Any, msg: int, wParam: int, lParam: int) -> int:
            if msg == WM_DROPFILES:
                hdrop = wParam
                try:
                    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
                    paths: list[Path] = []
                    for index in range(int(count)):
                        length = shell32.DragQueryFileW(hdrop, index, None, 0)
                        buf = ctypes.create_unicode_buffer(length + 1)
                        shell32.DragQueryFileW(hdrop, index, buf, length + 1)
                        paths.append(Path(buf.value))
                    for path in paths:
                        if path.suffix.casefold() in _PATCH_SUFFIXES:
                            gui.window.after(0, lambda p=path: _ingest_patch(gui, p))
                finally:
                    shell32.DragFinish(hdrop)
                return 0
            return int(call_proc(old_proc, hWnd, msg, wParam, lParam))

        callback = WNDPROC(wndproc)
        previous = set_long(HWND(hwnd), GWL_WNDPROC, ctypes.cast(callback, ctypes.c_void_p))
        if not previous:
            raise OSError("SetWindowLongPtrW(GWLP_WNDPROC) failed")
        # Use the value returned by SetWindowLongPtrW as the authoritative previous
        # procedure in case another component subclassed the Tk window between calls.
        old_proc = previous
        shell32.DragAcceptFiles(HWND(hwnd), True)
        gui._forge_drop_callback = callback
        gui._forge_drop_old_proc = old_proc
        gui._forge_drop_installed = True
        _safe_log(gui, "[PASS] Native Windows patch drag/drop enabled.", "pass")
    except Exception as exc:
        _safe_log(gui, f"[WARN] Native Windows patch drag/drop is unavailable: {exc}", "warn")


def _hide_legacy_header(gui: Any) -> None:
    """Remove only the legacy top title strip and its separator."""
    children = list(gui.window.winfo_children())
    main_body = getattr(gui, "main_body", None)
    hidden = False
    for child in children:
        if child is main_body:
            continue
        try:
            direct = {_widget_text(w).strip().upper() for w in child.winfo_children()}
        except Exception:
            direct = set()
        if "FORGEPY" in direct:
            try:
                child.pack_forget()
                hidden = True
            except Exception:
                pass
            break
    if hidden:
        for child in children:
            if child is main_body:
                continue
            try:
                if int(child.cget("height")) == 1 and str(child.cget("bg")).casefold() in {"#00d9ff", "cyan"}:
                    child.pack_forget()
                    break
            except Exception:
                continue


def _build_simplified_quick_actions(gui: Any, parent: Any) -> None:
    """Single compact quick bar; no duplicate title/action rows."""
    tk = gui.tk
    quick = gui._panel(parent)
    quick.pack(fill="x", padx=10, pady=(5, 5))
    row = tk.Frame(quick, bg="#11151a")
    row.pack(fill="x", padx=8, pady=5)
    gui._forge_quick_project = tk.Label(
        row, text=_project_label(gui), bg="#11151a", fg="#929aa3",
        font=("Segoe UI", 8), anchor="w",
    )
    gui._forge_quick_project.pack(side="left", padx=(2, 8))
    gui._button(row, "FULL GATE", lambda: gui._start_command("full"), primary=True, compact=True).pack(side="left", padx=(0, 4))
    gui._button(row, "BUILD", lambda: gui._start_command("build"), compact=True).pack(side="left", padx=4)
    gui._button(row, "RUN", lambda: gui._start_command("launch-gui"), compact=True).pack(side="left", padx=4)
    gui._button(row, "CHECK FOR UPDATES", lambda: _check_updates(gui), compact=True).pack(side="left", padx=4)
    gui._button(row, "Project CLI", gui._open_cli, compact=True).pack(side="right", padx=(4, 2))
    gui._button(row, "Refresh", gui._refresh_clicked, compact=True).pack(side="right", padx=4)
    gui.refresh_btn = _find_button(gui, "Refresh") or getattr(gui, "refresh_btn", None)
    gui.cli_btn = _find_button(gui, "Project CLI") or getattr(gui, "cli_btn", None)


def _build_simplified_status_bar(gui: Any, parent: Any) -> None:
    """One bottom status strip with project, Git/job state and global app version."""
    tk = gui.tk
    status = tk.Frame(parent, bg="#07090b", height=25, highlightthickness=1, highlightbackground="#20262d")
    status.pack(fill="x", side="bottom", padx=10, pady=(0, 5))
    status.pack_propagate(False)
    gui._forge_status_project = tk.Label(status, text=_project_label(gui), bg="#07090b", fg="#edf2f5", font=("Segoe UI", 8), anchor="w")
    gui._forge_status_project.pack(side="left", padx=(8, 9))
    gui._forge_status_git = tk.Label(status, text="", bg="#07090b", fg="#929aa3", font=("Consolas", 8), anchor="w")
    gui._forge_status_git.pack(side="left", padx=(0, 8))
    gui.footer = tk.Label(status, text="[Status:Loading]", bg="#07090b", fg="#00d9ff", font=("Consolas", 8), anchor="w")
    gui.footer.pack(side="left", fill="x", expand=True)
    try:
        from ForgeApplicationIdentity import DISPLAY_VERSION, DISPLAY_BUILD
        version_text = f"ForgePY {DISPLAY_VERSION} · {DISPLAY_BUILD}"
    except Exception:
        try:
            from ForgePYVersion import VERSION
            version_text = f"ForgePY {VERSION}"
        except Exception:
            version_text = "ForgePY"
    tk.Label(status, text=version_text, bg="#07090b", fg="#929aa3", font=("Consolas", 8)).pack(side="right", padx=8)
    gui._forge_status_last_run = tk.Label(status, text="Last: —", bg="#07090b", fg="#929aa3", font=("Consolas", 8), anchor="e")
    gui._forge_status_last_run.pack(side="right", padx=(6, 0))


def _native_windows_folder_photo(gui: Any, size: int = 16) -> Any | None:
    """Render the current Windows shell folder icon into a Tk PhotoImage.

    This avoids shipping a copied Windows asset while still presenting the real shell
    folder glyph the user expects.  Non-Windows systems simply use the text fallback.
    """
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
        flags = 0x000000100 | 0x000000001 | 0x000000010  # ICON | SMALLICON | USEFILEATTRIBUTES
        if not shell32.SHGetFileInfoW("C:\\", 0x10, ctypes.byref(info), ctypes.sizeof(info), flags):
            return None
        hdc = gdi32.CreateCompatibleDC(0)
        bits = ctypes.c_void_p()
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = size
        bmi.bmiHeader.biHeight = -size  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        bitmap = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), 0, 0)
        old = gdi32.SelectObject(hdc, bitmap)
        brush = gdi32.CreateSolidBrush(0x001A1511)  # COLORREF for PANEL #11151a
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


def _install_health_footer(gui: Any) -> None:
    tk = gui.tk
    host = getattr(gui, "health_host", None)
    if host is None:
        return
    footer = tk.Frame(host, bg="#11151a")
    footer.pack(side="bottom", fill="x", padx=8, pady=(4, 8))
    gui._forge_health_project = tk.Label(footer, text=str(gui.contract.name), bg="#11151a", fg="#edf2f5", font=("Segoe UI Semibold", 9), anchor="w")
    gui._forge_health_project.pack(fill="x")
    gui._forge_health_build = tk.Label(footer, text="", bg="#11151a", fg="#929aa3", font=("Consolas", 8), anchor="w")
    gui._forge_health_build.pack(fill="x", pady=(1, 5))
    actions = tk.Frame(footer, bg="#11151a")
    actions.pack(fill="x")
    folder_image = _native_windows_folder_photo(gui)
    drop = gui._button(actions, "" if folder_image is not None else "📁", lambda: _choose_patch(gui), compact=True)
    if folder_image is not None:
        gui._forge_folder_image = folder_image
        drop.configure(image=folder_image, compound="left")
    drop.configure(cursor="hand2")
    drop.pack(side="right", padx=(4, 0))
    gui._forge_patch_drop_button = drop
    gui._forge_debug_button = gui._button(actions, "DEBUG", lambda: _debug_clicked(gui), compact=True)
    gui._forge_debug_button.pack(side="left")
    try:
        from ForgePYVersion import VERSION
        version = VERSION
    except Exception:
        version = ""
    tk.Label(footer, text=f"v{version}", bg="#11151a", fg="#929aa3", font=("Consolas", 8), anchor="e").pack(fill="x", pady=(6, 0))


def _rewire_workspace_actions(gui: Any) -> None:
    for legacy_text in ("COMMIT + PUSH", "COMMIT + PUSH GREEN"):
        button = _find_button(gui, legacy_text)
        if button is not None:
            try:
                button.pack_forget()
            except Exception:
                pass
    button = _find_button(gui, "UPDATES")
    if button is not None:
        try:
            button.configure(text="CHECK FOR UPDATES", command=lambda: _check_updates(gui))
        except Exception:
            pass
    button = _find_button(gui, "DEBUG")
    if button is not None:
        try:
            button.configure(command=lambda: _debug_clicked(gui))
        except Exception:
            pass


def _build_simple_source_control(gui: Any, parent: Any) -> None:
    """Two-tab source-control UX: Local Source is default; GitHub is automated."""
    tk = gui.tk
    shell = tk.Frame(parent, bg="#090b0e")
    shell.pack(fill="both", expand=True, padx=16, pady=12)
    tabs = tk.Frame(shell, bg="#090b0e")
    tabs.pack(fill="x", pady=(0, 8))
    body = tk.Frame(shell, bg="#090b0e")
    body.pack(fill="both", expand=True)
    pages = {name: tk.Frame(body, bg="#090b0e") for name in ("Local Source", "GitHub")}

    def show(name: str) -> None:
        for page in pages.values():
            page.pack_forget()
        pages[name].pack(fill="both", expand=True)

    gui._button(tabs, "Local Source", lambda: show("Local Source"), primary=True, compact=True).pack(side="left", padx=(0, 5))
    gui._button(tabs, "GitHub", lambda: show("GitHub"), compact=True).pack(side="left", padx=5)

    _build_local_source_page(gui, pages["Local Source"])
    _build_github_page(gui, pages["GitHub"])
    show("Local Source")


def _build_local_source_page(gui: Any, parent: Any) -> None:
    tk = gui.tk
    title = tk.Label(parent, text="LOCAL SOURCE", bg="#090b0e", fg="#00d9ff", font=("Segoe UI Semibold", 13), anchor="w")
    title.pack(fill="x")
    tk.Label(parent, text="Certified local recovery/history. GitHub publication happens automatically after a GREEN Full Gate.", bg="#090b0e", fg="#929aa3", font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(2, 10))
    summary = tk.Label(parent, text="", bg="#171c22", fg="#edf2f5", font=("Consolas", 9), justify="left", anchor="nw", padx=12, pady=10)
    summary.pack(fill="x", pady=(0, 10))

    def refresh() -> None:
        root = Path(gui.root_path)
        st = _source_status(root)
        project_id = str(getattr(gui.contract, "project_id", root.name))
        try:
            from ForgeLocalSource import summary as local_status
            local = local_status(root, project_id)
        except Exception:
            local = {}
        summary.configure(text=(
            f"Project : {gui.contract.name}\n"
            f"Branch  : {st.get('branch') or '-'}\n"
            f"Head    : {st.get('headShort') or '-'}\n"
            f"Tree    : {'CLEAN' if st.get('clean') else 'DIRTY'}\n"
            f"Backup  : {'READY' if local.get('repositoryReady') else 'NOT INITIALIZED'}"
        ))

    row = tk.Frame(parent, bg="#090b0e"); row.pack(fill="x", pady=(0, 6))
    gui._button(row, "BACKUP SOURCE", lambda: _backup_local(gui), primary=True, compact=True).pack(side="left", padx=(0, 5))
    gui._button(row, "RESTORE SOURCE", lambda: _restore_local(gui), compact=True).pack(side="left", padx=5)
    gui._button(row, "CREATE BRANCH", lambda: _create_branch(gui), compact=True).pack(side="left", padx=5)
    gui._button(row, "SWITCH BRANCH", lambda: _switch_branch(gui), compact=True).pack(side="left", padx=5)
    gui._button(row, "Refresh", refresh, compact=True).pack(side="right")
    refresh()



def _local_branch_names(gui: Any) -> list[str]:
    try:
        from ForgeLocalSource import branch_names
        return list(branch_names(Path(gui.root_path)) or [])
    except Exception:
        return []


def _create_branch(gui: Any) -> None:
    current = _branch(Path(gui.root_path)) or "main"
    name = gui._ask_text("Create Branch", "New branch name:", initial="feature/")
    if not name or not name.strip():
        return
    start = gui._ask_text("Create Branch", "Start from branch/revision:", initial=current) or current
    try:
        from ForgeGit import create_branch
        cp = create_branch(Path(gui.root_path), name.strip(), start.strip(), switch=True)
        _safe_log(gui, cp.stdout or "", "pass" if cp.returncode == 0 else "fail")
        if cp.returncode == 0:
            _refresh_compact_status(gui)
            gui._popup("Local Source", f"Created and switched to {name.strip()}.", kind="success")
        else:
            gui._popup("Local Source", cp.stdout or "Branch creation failed.", kind="error")
    except Exception as exc:
        gui._popup("Local Source", f"Branch creation failed:\n{exc}", kind="error")


def _switch_branch(gui: Any) -> None:
    names = _local_branch_names(gui)
    current = _branch(Path(gui.root_path))
    hint = ", ".join(names[:8]) if names else "main"
    name = gui._ask_text("Switch Branch", f"Branch name ({hint}):", initial=current or "main")
    if not name or not name.strip() or name.strip() == current:
        return
    try:
        from ForgeGit import switch_branch
        cp = switch_branch(Path(gui.root_path), name.strip())
        _safe_log(gui, cp.stdout or "", "pass" if cp.returncode == 0 else "fail")
        if cp.returncode == 0:
            _refresh_compact_status(gui)
            gui._popup("Local Source", f"Switched to {name.strip()}.", kind="success")
        else:
            gui._popup("Local Source", cp.stdout or "Branch switch failed. Resolve working changes first.", kind="warning")
    except Exception as exc:
        gui._popup("Local Source", f"Branch switch failed:\n{exc}", kind="error")

def _backup_local(gui: Any) -> None:
    root = Path(gui.root_path)
    project_id = str(getattr(gui.contract, "project_id", root.name))
    names = _local_branch_names(gui)
    current = _branch(root) or (names[0] if names else "main")
    branch = gui._ask_text(
        "Backup Source",
        f"Branch to back up ({', '.join(names[:8]) or current}):",
        initial=current,
    )
    if not branch or not branch.strip():
        return
    try:
        from ForgeLocalSource import backup_branch
        cp = backup_branch(root, project_id, branch.strip())
        _safe_log(gui, cp.stdout or "", "pass" if cp.returncode == 0 else "fail")
        gui._popup(
            "Local Source",
            "Local source backup completed." if cp.returncode == 0 else (cp.stdout or "Backup failed."),
            kind="success" if cp.returncode == 0 else "error",
        )
    except Exception as exc:
        gui._popup("Local Source", f"Backup failed:\n{exc}", kind="error")


def _restore_local(gui: Any) -> None:
    root = Path(gui.root_path)
    project_id = str(getattr(gui.contract, "project_id", root.name))
    branch = gui._ask_text("Restore Source", "Local Source branch to recover:", initial=_branch(root) or "main")
    if not branch or not branch.strip():
        return
    local = gui._ask_text("Restore Source", "Create recovery branch as:", initial=f"local-source-restore/{branch.strip().replace('/', '-')}")
    if not local or not local.strip():
        return
    if not gui._popup(
        "Restore Source",
        f"Recover Local Source branch '{branch.strip()}' into a new working-tree branch '{local.strip()}'?\n\nCurrent files are not force-reset.",
        kind="warning", confirm=True,
    ):
        return
    try:
        from ForgeLocalSource import restore_branch
        cp = restore_branch(root, project_id, branch.strip(), local.strip())
        _safe_log(gui, cp.stdout or "", "pass" if cp.returncode == 0 else "fail")
        gui._popup("Restore Source", cp.stdout or ("Recovery branch created." if cp.returncode == 0 else "Restore failed."), kind="success" if cp.returncode == 0 else "error")
        _refresh_compact_status(gui)
    except Exception as exc:
        gui._popup("Restore Source", f"Restore failed:\n{exc}", kind="error")


def _build_github_page(gui: Any, parent: Any) -> None:
    tk = gui.tk
    tk.Label(parent, text="GITHUB", bg="#090b0e", fg="#00d9ff", font=("Segoe UI Semibold", 13), anchor="w").pack(fill="x")
    tk.Label(parent, text="Remote backup/restore. Normal GREEN Full Gates commit and push the active branch automatically.", bg="#090b0e", fg="#929aa3", font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(2, 10))
    summary = tk.Label(parent, text="", bg="#171c22", fg="#edf2f5", font=("Consolas", 9), justify="left", anchor="nw", padx=12, pady=10)
    summary.pack(fill="x", pady=(0, 10))

    def refresh() -> None:
        st = _source_status(Path(gui.root_path))
        sync = "MATCH" if st.get("githubConfigured") and st.get("ahead") in {None, 0} and st.get("behind") in {None, 0} else "CHECK"
        summary.configure(text=(
            f"Branch     : {st.get('branch') or '-'}\n"
            f"Head       : {st.get('headShort') or '-'}\n"
            f"GitHub     : {'CONFIGURED' if st.get('githubConfigured') else 'NOT CONFIGURED'}\n"
            f"Sync       : {sync}\n"
            f"Auto GREEN : ON"
        ))

    row = tk.Frame(parent, bg="#090b0e"); row.pack(fill="x")
    gui._button(row, "BACKUP TO GITHUB", lambda: _backup_github(gui), primary=True, compact=True).pack(side="left", padx=(0, 5))
    gui._button(row, "RESTORE FROM GITHUB", lambda: _restore_github(gui), compact=True).pack(side="left", padx=5)
    gui._button(row, "Refresh", refresh, compact=True).pack(side="right")
    refresh()


def _backup_github(gui: Any) -> None:
    root = Path(gui.root_path)
    names = _local_branch_names(gui)
    current = _branch(root) or (names[0] if names else "main")
    branch = gui._ask_text(
        "Backup to GitHub",
        f"Branch to back up ({', '.join(names[:8]) or current}):",
        initial=current,
    )
    if not branch or not branch.strip():
        return
    try:
        from ForgeLocalSource import backup_github_branch
        cp = backup_github_branch(root, branch.strip())
        _safe_log(gui, cp.stdout or "", "pass" if cp.returncode == 0 else "fail")
        gui._popup(
            "GitHub",
            cp.stdout or ("GitHub backup complete." if cp.returncode == 0 else "GitHub backup failed."),
            kind="success" if cp.returncode == 0 else "warning",
        )
    except Exception as exc:
        gui._popup("GitHub", f"Backup failed:\n{exc}", kind="error")


def _restore_github(gui: Any) -> None:
    root = Path(gui.root_path)
    st = _source_status(root)
    current = str(st.get("branch") or "main")
    branch = gui._ask_text("Restore from GitHub", "GitHub branch to restore/synchronize:", initial=current)
    if not branch or not branch.strip():
        return
    if not gui._popup(
        "Restore from GitHub",
        f"Restore '{branch.strip()}' from GitHub using fast-forward-only safety?\n\n"
        "ForgePY will not force-reset or overwrite divergent local history.",
        kind="warning", confirm=True,
    ):
        return
    try:
        from ForgeLocalSource import restore_github_branch
        cp = restore_github_branch(root, branch.strip())
        _safe_log(gui, cp.stdout or "", "pass" if cp.returncode == 0 else "fail")
        gui._popup(
            "GitHub",
            cp.stdout or ("GitHub restore complete." if cp.returncode == 0 else "GitHub restore stopped safely."),
            kind="success" if cp.returncode == 0 else "warning",
        )
        _refresh_compact_status(gui)
    except Exception as exc:
        gui._popup("GitHub", f"Restore failed:\n{exc}", kind="error")



def _certified_project_tools(gui: Any) -> dict[str, list[Any]]:
    """Return only audited/certified tool specs; discovery alone never creates UI."""
    project_id = str(getattr(gui.contract, "project_id", gui.root_path.name))
    try:
        from ForgeToolRegistry import load
        tools = list(load(project_id) or [])
    except Exception:
        return {}
    grouped: dict[str, list[Any]] = {}
    for tool in tools:
        state = str(getattr(tool, "state", "") or "").upper()
        if state != "VERIFIED":
            continue
        category = str(getattr(tool, "category", "") or "Project Tools").strip() or "Project Tools"
        grouped.setdefault(category, []).append(tool)
    for rows in grouped.values():
        rows.sort(key=lambda t: str(getattr(t, "name", "") or getattr(t, "tool_id", "")).casefold())
    return dict(sorted(grouped.items(), key=lambda kv: kv[0].casefold()))


def _run_certified_tool(gui: Any, tool: Any) -> None:
    if getattr(gui, "_busy", False):
        gui._popup("Project Tool", "Finish or stop the active operation first.", kind="warning")
        return
    name = str(getattr(tool, "name", "") or getattr(tool, "tool_id", "Project Tool"))
    mutates = bool(getattr(tool, "mutates", False) or getattr(tool, "destructive", False))
    if mutates and not gui._popup(
        "Project Tool",
        f"Run certified project tool '{name}'?\n\nThis tool is declared as a write operation by the project adapter.",
        kind="warning", confirm=True,
    ):
        return
    _safe_log(gui, f"[INFO] Running certified project tool: {name}", "info")

    def worker() -> None:
        lines: list[str] = []
        try:
            from ForgeToolRegistry import run_tool
            rc = int(run_tool(tool, emit=lambda line: lines.append(str(line))))
            _dispatch_main(gui, lambda: _finish_certified_tool(gui, name, rc, lines))
        except Exception as exc:
            _dispatch_main(gui, lambda: _finish_certified_tool(gui, name, 1, lines + [str(exc)]))

    threading.Thread(target=worker, daemon=True, name="ForgeCertifiedProjectTool").start()


def _finish_certified_tool(gui: Any, name: str, rc: int, lines: list[str]) -> None:
    for line in lines:
        _safe_log(gui, line, "pass" if "PASS" in line.upper() else ("fail" if "FAIL" in line.upper() else "info"))
    gui._popup("Project Tool", f"{name}\n\n{'Completed successfully.' if rc == 0 else 'Failed. See the ForgePY console for details.'}", kind="success" if rc == 0 else "error")


def _open_project_tool_category(gui: Any, category: str, tools: list[Any]) -> None:
    tk = gui.tk
    try:
        overlay, shell = gui._embedded_action_shell(f"{gui.contract.name} · {category}", kind="info", width=760, height=min(620, 180 + len(tools) * 54))
    except Exception:
        return
    tk.Label(shell, text="CERTIFIED PROJECT OPERATIONS", bg="#11151a", fg="#00d9ff", font=("Segoe UI Semibold", 9), anchor="w").pack(fill="x", padx=16, pady=(4, 8))
    for tool in tools:
        row = tk.Frame(shell, bg="#171c22")
        row.pack(fill="x", padx=16, pady=3)
        name = str(getattr(tool, "name", "") or getattr(tool, "tool_id", "Project Tool"))
        cap = str(getattr(tool, "capability", "") or "")
        tk.Label(row, text=name, bg="#171c22", fg="#edf2f5", font=("Segoe UI Semibold", 9), anchor="w").pack(side="left", fill="x", expand=True, padx=(10, 6), pady=8)
        if cap:
            tk.Label(row, text=cap, bg="#171c22", fg="#929aa3", font=("Segoe UI", 8)).pack(side="left", padx=6)
        gui._button(row, "Run", lambda t=tool: _run_certified_tool(gui, t), compact=True).pack(side="right", padx=8, pady=5)
    actions = tk.Frame(shell, bg="#11151a"); actions.pack(fill="x", padx=16, pady=(10, 14))
    gui._button(actions, "Close", lambda: gui._finish_embedded_action(overlay), compact=True).pack(side="right")


def _refresh_project_tool_rail(gui: Any) -> None:
    host = getattr(gui, "_forge_project_tool_host", None)
    if host is None:
        return
    try:
        for child in host.winfo_children():
            child.destroy()
    except Exception:
        return
    groups = _certified_project_tools(gui)
    if not groups:
        return
    tk = gui.tk
    tk.Label(host, text="PROJECT TOOLS", bg="#11151a", fg="#929aa3", font=("Segoe UI Semibold", 8), anchor="w").pack(fill="x", padx=12, pady=(9, 4))
    for category, tools in groups.items():
        btn = gui._button(host, category, lambda c=category, rows=tools: _open_project_tool_category(gui, c, rows), compact=True)
        try:
            btn.configure(anchor="w")
        except Exception:
            pass
        btn.pack(fill="x", padx=7, pady=2)


def _install_project_tool_rail(gui: Any) -> None:
    if getattr(gui, "_forge_project_tool_host", None) is not None:
        _refresh_project_tool_rail(gui)
        return
    parent = getattr(gui, "app_nav_host", None)
    if parent is None:
        return
    gui._forge_project_tool_host = gui.tk.Frame(parent, bg="#11151a")
    gui._forge_project_tool_host.pack(fill="x", side="bottom", pady=(4, 8))
    _refresh_project_tool_rail(gui)


def _refresh_compatibility_snapshot(gui: Any) -> None:
    try:
        from ForgeCompatibilitySnapshot import refresh
        payload = refresh(
            Path(gui.root_path),
            str(getattr(gui.contract, "project_id", gui.root_path.name)),
            str(getattr(gui.contract, "name", gui.root_path.name)),
        )
        _safe_log(gui, f"[PASS] ForgePY compatibility reference current: {payload.get('forgePyBuild')} ({payload.get('path')})", "pass")
    except Exception as exc:
        _safe_log(gui, f"[WARN] Compatibility reference could not be refreshed: {exc}", "warn")

def _dark_scrollbars(gui: Any) -> None:
    try:
        style = gui.ttk.Style(gui.window)
        for name in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            style.configure(name, background="#28313a", troughcolor="#11151a", bordercolor="#11151a", arrowcolor="#edf2f5", darkcolor="#28313a", lightcolor="#28313a")
            style.map(name, background=[("active", "#3a4652")])
    except Exception:
        pass


def _normalize_classic_scrollbars(gui: Any) -> None:
    for widget in _walk_widgets(gui.window):
        try:
            if widget.winfo_class() != "Scrollbar":
                continue
            widget.configure(
                bg="#28313a", activebackground="#3a4652", troughcolor="#11151a",
                highlightbackground="#11151a", highlightcolor="#11151a", bd=0, relief="flat",
            )
        except Exception:
            pass


def _normalize_console_ratio(gui: Any) -> None:
    """Reduce the legacy default console footprint while preserving deliberate user resize."""
    panes = getattr(gui, "global_workspace_panes", None)
    if panes is None:
        return
    try:
        from ForgePYSettings import load_settings, set_section
        ui = load_settings().get("ui") or {}
        raw = ui.get("globalConsoleRatio")
        ratio = float(raw) if raw is not None else 0.34
        if raw is None or 0.32 <= ratio <= 0.36:
            ratio = 0.27
            set_section("ui", {"globalConsoleRatio": ratio})
        panes.update_idletasks()
        width = max(760, int(panes.winfo_width()))
        panes.sash_place(0, max(420, int(width * (1.0 - ratio))), 0)
    except Exception:
        pass



def _native_windows_popup(gui: Any, title: str, message: str, *, kind: str = "info", confirm: bool = False, parent: Any | None = None) -> bool:
    """Use Tk's Windows-native messagebox bridge, never a direct ctypes MessageBox call.

    Python 3.14 is stricter about GIL/thread-state re-entry around foreign calls.  Calling
    user32.MessageBoxW through ctypes can release the GIL while Windows pumps messages,
    which can re-enter Tk/Python and crash with PyEval_RestoreThread.  tkinter.messagebox
    keeps the modal prompt inside Tk's supported interpreter/thread boundary while still
    rendering as the normal Windows prompt.
    """
    if os.name != "nt":
        raise OSError("native Windows prompt requested on a non-Windows host")
    owner = parent if parent is not None else getattr(gui, "window", None)
    box = getattr(gui, "messagebox", None)
    if box is None:
        raise RuntimeError("Tk messagebox bridge is unavailable")

    options: dict[str, Any] = {"parent": owner} if owner is not None else {}
    normalized = str(kind or "info").casefold()
    if confirm:
        # Safe default: pressing Enter before choosing should not mutate source.
        options["default"] = "no"
        return bool(box.askyesno(str(title), str(message), **options))
    if normalized == "error":
        box.showerror(str(title), str(message), **options)
    elif normalized == "warning":
        box.showwarning(str(title), str(message), **options)
    else:
        box.showinfo(str(title), str(message), **options)
    return True


def _responsive_embedded_popup(gui: Any, title: str, message: str, *, kind: str = "info", confirm: bool = False, parent: Any | None = None) -> bool:
    """Cross-platform fallback with a footer that can never be consumed by content."""
    tk = gui.tk
    # Estimate useful size, then let the responsive shell wrapper clamp it to the host.
    logical_lines = 0
    for line in str(message).splitlines() or [""]:
        logical_lines += max(1, (len(line) + 69) // 70)
    height = max(290, min(620, 185 + logical_lines * 19))
    overlay, shell = gui._embedded_action_shell(title, kind=kind, width=650, height=height)
    result = tk.BooleanVar(master=gui.window, value=False)
    done = tk.BooleanVar(master=gui.window, value=False)

    def close(value: bool) -> None:
        result.set(bool(value))
        gui._finish_embedded_action(overlay)
        done.set(True)

    # Pack the action footer FIRST at the bottom.  Content can scroll/shrink, buttons cannot.
    actions = tk.Frame(shell, bg="#11151a")
    actions.pack(side="bottom", fill="x", padx=16, pady=(8, 16))
    if confirm:
        gui._button(actions, "No", lambda: close(False), compact=True).pack(side="right", padx=(8, 0))
        gui._button(actions, "Yes", lambda: close(True), primary=True, compact=True).pack(side="right")
    else:
        gui._button(actions, "OK", lambda: close(True), primary=True, compact=True).pack(side="right")

    body = tk.Frame(shell, bg="#11151a")
    body.pack(fill="both", expand=True, padx=16, pady=(0, 4))
    text = tk.Text(
        body, bg="#11151a", fg="#929aa3", insertbackground="#00d9ff", relief="flat", bd=0,
        wrap="word", font=("Segoe UI", 10), height=max(4, min(18, logical_lines + 1)),
        highlightthickness=0, takefocus=False,
    )
    scroll = gui.ttk.Scrollbar(body, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    text.insert("1.0", str(message))
    text.configure(state="disabled")

    shell.bind("<Escape>", lambda _e: close(False))
    shell.bind("<Return>", lambda _e: close(True))
    shell.focus_set()
    gui.window.wait_variable(done)
    return bool(result.get())


def _responsive_ask_text(gui: Any, title: str, prompt: str, *, initial: str = "", parent: Any | None = None) -> str | None:
    """Text-entry prompt that never destroys an already-open ForgePY action surface."""
    # Patch Review and other specialist surfaces are themselves embedded overlays.
    # Creating another embedded shell would destroy the parent overlay/tree and leave
    # its callbacks holding dead Tcl widget names. Use Tk's independent text prompt
    # whenever an action surface is already active.
    if bool(getattr(gui, "_embedded_action_active", False)):
        try:
            value = gui.simpledialog.askstring(
                title, str(prompt), initialvalue=str(initial or ""), parent=gui.window
            )
            if value is None:
                return None
            value = str(value).strip()
            return value or None
        except Exception as exc:
            _safe_log(gui, f"[WARN] Text prompt fallback failed: {exc}", "warn")
            return None
    tk = gui.tk
    logical_lines = sum(max(1, (len(line) + 69) // 70) for line in (str(prompt).splitlines() or [""]))
    height = max(300, min(560, 215 + logical_lines * 18))
    overlay, shell = gui._embedded_action_shell(title, kind="info", width=650, height=height)
    result: list[str | None] = [None]
    done = tk.BooleanVar(master=gui.window, value=False)

    def close(ok: bool) -> None:
        value = entry_var.get().strip()
        result[0] = value if ok and value else None
        gui._finish_embedded_action(overlay)
        done.set(True)

    actions = tk.Frame(shell, bg="#11151a")
    actions.pack(side="bottom", fill="x", padx=18, pady=(8, 16))
    gui._button(actions, "Cancel", lambda: close(False), compact=True).pack(side="right", padx=(8, 0))
    gui._button(actions, "Continue", lambda: close(True), primary=True, compact=True).pack(side="right")

    body = tk.Frame(shell, bg="#11151a")
    body.pack(fill="both", expand=True, padx=18, pady=(0, 8))
    tk.Message(body, text=str(prompt), bg="#11151a", fg="#929aa3", font=("Segoe UI", 9), width=575, anchor="w", justify="left").pack(fill="x", pady=(0, 10))
    entry_var = tk.StringVar(master=gui.window, value=initial)
    entry = tk.Entry(body, textvariable=entry_var, bg="#07090b", fg="#edf2f5", insertbackground="#00d9ff", relief="flat", bd=0, font=("Consolas", 10))
    entry.pack(fill="x", ipady=8)
    entry.bind("<Escape>", lambda _e: close(False))
    entry.bind("<Return>", lambda _e: close(True))
    entry.focus_set()
    gui.window.wait_variable(done)
    return result[0]


def _clamped_embedded_shell(gui: Any, original: Callable[..., Any], title: str, *, kind: str = "info", width: int = 570, height: int = 250) -> tuple[Any, Any]:
    """Clamp every ForgePY-owned embedded surface to the visible center workspace."""
    host = getattr(gui, "center_host", getattr(gui, "window", None))
    try:
        host.update_idletasks()
        available_w = int(host.winfo_width())
        available_h = int(host.winfo_height())
        if available_w < 300 or available_h < 220:
            gui.window.update_idletasks()
            available_w = max(available_w, int(gui.window.winfo_width()))
            available_h = max(available_h, int(gui.window.winfo_height()))
        max_w = max(420, available_w - 40)
        max_h = max(250, available_h - 40)
        width = max(420, min(int(width), max_w))
        height = max(250, min(int(height), max_h))
    except Exception:
        width = max(420, int(width))
        height = max(250, int(height))
    return original(gui, title, kind=kind, width=width, height=height)

def _registry_root_for_patch_target(gui: Any, target: str) -> Path | None:
    """Resolve a patch project id/name/root alias against the live registry."""
    wanted = str(target or "").strip().casefold()
    if not wanted:
        return None
    try:
        entries = list(gui.registry.entries() or [])
    except Exception:
        entries = []
    for entry in entries:
        try:
            root = Path(entry.root).expanduser().resolve()
        except Exception:
            continue
        aliases = {
            str(getattr(entry, "project_id", "") or "").strip().casefold(),
            str(getattr(entry, "name", "") or "").strip().casefold(),
            root.name.casefold(),
            str(root).casefold(),
        }
        if wanted in aliases:
            return root
    # The active project may have been rebound after the registry snapshot.
    try:
        root = Path(gui.root_path).expanduser().resolve()
        contract = getattr(gui, "contract", None)
        aliases = {root.name.casefold(), str(root).casefold()}
        aliases.add(str(getattr(contract, "project_id", "") or "").strip().casefold())
        aliases.add(str(getattr(contract, "name", "") or "").strip().casefold())
        if wanted in aliases:
            return root
    except Exception:
        pass
    return None


def _report_tk_callback_exception(gui: Any, exc_type: type[BaseException], exc_value: BaseException, tb: Any) -> None:
    """Route Tk callback failures into the ForgePY Project Console instead of stderr."""
    text = "".join(traceback.format_exception(exc_type, exc_value, tb)).rstrip()
    _safe_log(gui, "[FAIL] Tkinter callback exception:\n" + text, "fail")
    try:
        gui.footer.configure(text="[GUI:Callback Error — see Project Console]", fg="#ff5d68")
    except Exception:
        pass


def _install_unbuffered_provider_output() -> None:
    """Force Python project providers/operation-host descendants to stream live output."""
    try:
        from PCCSurfaceCommon import BackendClient
    except Exception:
        return
    if getattr(BackendClient, "_forge_unbuffered_output_installed", False):
        return
    original = BackendClient._embedded_env
    def embedded_env(self: Any) -> dict[str, str]:
        env = dict(original(self))
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return env
    BackendClient._embedded_env = embedded_env
    BackendClient._forge_unbuffered_output_installed = True


def install_forge_gui(cls: type[Any]) -> type[Any]:
    """Install the simplified UX once on the canonical ForgeGui class."""
    if getattr(cls, "_forge_f60r415_installed", False):
        return cls
    cls._forge_f60r415_installed = True

    original_styles = cls._configure_styles
    original_shell = cls._build_shell
    original_workspace = cls._build_workspace_tab
    original_activate = cls._activate_project
    original_start_command = cls._start_command
    original_drain_events = cls._drain_events
    original_popup = cls._popup
    original_ask_text = cls._ask_text
    original_embedded_action_shell = cls._embedded_action_shell
    original_open_patch_review = getattr(cls, "_open_patch_review", None)

    def start_command(self: Any, command: str, *args: Any, **kwargs: Any) -> Any:
        if str(command or "") == "full":
            before = _latest_debug(Path(self.root_path))
            self._forge_debug_before_full = str(before) if before else ""
            self._forge_full_gate_generation = int(getattr(self, "_forge_full_gate_generation", 0) or 0) + 1
            self._forge_full_gate_last_success_generation = -1
        return original_start_command(self, command, *args, **kwargs)

    def configure_styles(self: Any) -> None:
        original_styles(self)
        _dark_scrollbars(self)

    def embedded_action_shell(self: Any, title: str, *, kind: str = "info", width: int = 570, height: int = 250) -> tuple[Any, Any]:
        return _clamped_embedded_shell(self, original_embedded_action_shell, title, kind=kind, width=width, height=height)

    def popup(self: Any, title: str, message: str, *, kind: str = "info", confirm: bool = False, parent: Any | None = None) -> bool:
        if os.name == "nt":
            try:
                return _native_windows_popup(self, title, message, kind=kind, confirm=confirm, parent=parent)
            except Exception as exc:
                _safe_log(self, f"[WARN] Native Windows prompt failed; using responsive ForgePY fallback: {exc}", "warn")
        return _responsive_embedded_popup(self, title, message, kind=kind, confirm=confirm, parent=parent)

    def ask_text(self: Any, title: str, prompt: str, *, initial: str = "", parent: Any | None = None) -> str | None:
        return _responsive_ask_text(self, title, prompt, initial=initial, parent=parent)

    def open_patch_review(self: Any) -> None:
        if original_open_patch_review is None:
            self._popup("Patch Review", "Patch Review is unavailable in this build.", kind="error")
            return
        original_open_patch_review(self)
        # User-facing wording reflects what the authoritative action actually does.
        def relabel() -> None:
            mapping = {
                "Queue": "Approve",
                "Queue + Apply": "Approve + Apply + Gate",
            }
            for old_text, new_text in mapping.items():
                button = _find_button(self, old_text)
                if button is not None:
                    try: button.configure(text=new_text)
                    except Exception: pass
        _call_later(self, 20, relabel)

    def build_source_control(self: Any, parent: Any) -> None:
        _build_simple_source_control(self, parent)

    def build_quick_actions(self: Any, parent: Any) -> None:
        _build_simplified_quick_actions(self, parent)

    def build_statusbar(self: Any, parent: Any) -> None:
        _build_simplified_status_bar(self, parent)

    def drain_events(self: Any) -> None:
        original_drain_events(self)
        _drain_main_actions(self)

    def build_workspace(self: Any, parent: Any) -> None:
        original_workspace(self, parent)
        _rewire_workspace_actions(self)

    def activate_project(self: Any, root: Path) -> None:
        original_activate(self, root)
        _call_later(self, 100, lambda: _refresh_compact_status(self))
        _call_later(self, 180, lambda: _refresh_project_tool_rail(self))
        _call_later(self, 350, lambda: _refresh_compatibility_snapshot(self))

    def build_shell(self: Any) -> None:
        self._forge_main_actions = queue.Queue()
        original_shell(self)
        try:
            self.window.report_callback_exception = lambda exc_type, exc_value, tb: _report_tk_callback_exception(self, exc_type, exc_value, tb)
        except Exception:
            pass
        _hide_legacy_header(self)
        _install_health_footer(self)
        _install_project_tool_rail(self)
        _normalize_classic_scrollbars(self)
        try:
            dashboard_button = self._app_tab_buttons.get("Project Workspace") or self._app_tab_buttons.get("Workspace")
            if dashboard_button is not None:
                dashboard_button.configure(text="Dashboard")
        except Exception:
            pass
        _rewire_workspace_actions(self)
        if not isinstance(getattr(self, "_event_q", None), _EventQueueProxy):
            self._event_q = _EventQueueProxy(self, self._event_q)
        _call_later(self, 250, lambda: _install_windows_drop(self))
        _call_later(self, 180, lambda: _normalize_console_ratio(self))
        _call_later(self, 300, lambda: _refresh_compact_status(self))
        _call_later(self, 420, lambda: _normalize_classic_scrollbars(self))
        _call_later(self, 650, lambda: _refresh_compatibility_snapshot(self))

    cls._start_command = start_command
    cls._configure_styles = configure_styles
    cls._embedded_action_shell = embedded_action_shell
    cls._popup = popup
    cls._ask_text = ask_text
    cls._activate_project = activate_project
    cls._drain_events = drain_events
    cls._build_global_quick_actions = build_quick_actions
    cls._build_global_statusbar = build_statusbar
    cls._build_source_control_tab = build_source_control
    cls._build_workspace_tab = build_workspace
    cls._registry_root_for_patch_target = lambda self, target: _registry_root_for_patch_target(self, target)
    cls._open_patch_review = open_patch_review
    cls._build_shell = build_shell
    cls._forge_check_updates = _check_updates
    cls._forge_ingest_patch = _ingest_patch
    cls._forge_debug_reveal = _debug_clicked

    if hasattr(cls, "_set_health_rail_collapsed"):
        def keep_health_visible(self: Any, collapsed: bool = False) -> None:
            try:
                self.health_host.pack(side="right", fill="y")
                self._health_rail_collapsed = False
            except Exception:
                pass
        cls._set_health_rail_collapsed = keep_health_visible
    if hasattr(cls, "_toggle_health_rail"):
        cls._toggle_health_rail = lambda self: None
    _install_unbuffered_provider_output()
    from ForgeF440Normalization import install_normalization
    install_normalization(cls)
    return cls
