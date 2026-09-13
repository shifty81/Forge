#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

STATUS_CACHE_VERSION = "FORGEPY-STATUS-CACHE-1.1-F562"
_LOCK = threading.RLock()
_SOURCE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_AUTO_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _key(root: Path) -> str:
    return os.path.normcase(str(root.expanduser().resolve()))


def clear(root: Path | None = None) -> None:
    with _LOCK:
        if root is None:
            _SOURCE_CACHE.clear()
            _AUTO_CACHE.clear()
            return
        key = _key(root)
        _SOURCE_CACHE.pop(key, None)
        _AUTO_CACHE.pop(key, None)


def _settings() -> dict[str, Any]:
    try:
        from ForgePYSettings import load_settings
        value = load_settings()
        return dict(value or {})
    except Exception:
        return {}


def git_binary() -> str:
    """Return the configured Git executable, falling back to PATH.

    Compact GUI state must honor the same source-control configuration as the
    authoritative source-control service. A user-selected Git binary is valid even
    when git.exe is not globally on PATH.
    """
    configured = str(((_settings().get("sourceControl") or {}).get("gitBinary") or "")).strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            try:
                return str(candidate.resolve())
            except Exception:
                return str(candidate)
    return shutil.which("git") or ""


def _quiet_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
    info.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
    return info


def _run_git(root: Path, args: list[str], timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    git = git_binary()
    if not git:
        return subprocess.CompletedProcess([], 127, stdout="Git executable not configured or found on PATH.\n")
    return subprocess.run(
        [git, "-C", str(root), *args],
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
        creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0,
        startupinfo=_quiet_startupinfo(),
    )


def _remote_kind(name: str, url: str) -> str:
    low_name = str(name or "").casefold()
    low = str(url or "").casefold()
    if "github.com" in low:
        return "github"

    sc = _settings().get("sourceControl") or {}
    forgegit_names = {
        str(sc.get("defaultForgeGitRemote") or "forgegit").strip().casefold(),
        str(sc.get("defaultInternalGitRemote") or "forgepy-internal").strip().casefold(),
        "forgegit",
        "forgepy-internal",
    }
    if low_name in forgegit_names:
        return "forgegit"

    for raw_root in (
        str(sc.get("forgeGitRoot") or "").strip(),
        str(sc.get("internalGitRoot") or "").strip(),
    ):
        if not raw_root or not url:
            continue
        try:
            remote_path = Path(url).expanduser().resolve()
            if remote_path.is_relative_to(Path(raw_root).expanduser().resolve()):
                return "forgegit"
        except Exception:
            pass

    forgejo_name = str(sc.get("defaultForgejoRemote") or "forgejo").strip().casefold()
    hosts = {
        token.strip().casefold()
        for token in str(os.environ.get("VAULT_FORGEJO_HOSTS") or "").split(";")
        if token.strip()
    }
    if low_name == forgejo_name or "forgejo" in low_name or "forgejo" in low:
        return "forgejo"
    if any(token in low for token in ("localhost", "127.0.0.1", "::1")):
        return "forgejo"
    if any(host in low for host in hosts):
        return "forgejo"
    return "other"


def _declared_github(root: Path) -> dict[str, str]:
    try:
        from ForgeProjectSource import declared_project_github
        return dict(declared_project_github(root) or {})
    except Exception:
        return {"remote": "", "cloneUrl": "", "webUrl": ""}


def _parse_porcelain_v2(text: str) -> dict[str, Any]:
    branch = ""
    upstream = ""
    head = ""
    ahead = behind = None
    staged = unstaged = untracked = 0
    for line in text.splitlines():
        if line.startswith("# branch.oid "):
            value = line[len("# branch.oid "):].strip()
            head = "" if value in {"(initial)", "(unknown)"} else value
            continue
        if line.startswith("# branch.head "):
            value = line[len("# branch.head "):].strip()
            branch = "" if value == "(detached)" else value
            continue
        if line.startswith("# branch.upstream "):
            upstream = line[len("# branch.upstream "):].strip()
            continue
        if line.startswith("# branch.ab "):
            match = re.search(r"\+(\d+)\s+-(\d+)", line)
            if match:
                ahead, behind = int(match.group(1)), int(match.group(2))
            continue
        if line.startswith("? "):
            untracked += 1
            continue
        if line.startswith(("1 ", "2 ", "u ")):
            parts = line.split(" ", 2)
            xy = parts[1] if len(parts) > 1 else ".."
            if len(xy) >= 1 and xy[0] not in {".", " "}:
                staged += 1
            if len(xy) >= 2 and xy[1] not in {".", " "}:
                unstaged += 1
    return {
        "hasHead": bool(head),
        "branch": branch,
        "head": head,
        "headShort": head[:12],
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "clean": staged == 0 and unstaged == 0 and untracked == 0,
    }


def fast_source_status(root: Path, *, ttl: float = 2.5, force: bool = False) -> dict[str, Any]:
    """Compact source state for navigation/status cards.

    This intentionally uses a bounded read-only path. Exact source-control operations
    still use ForgeSourceControl. The configured Git executable is honored, and remote
    classification follows ForgePY source-control settings.
    """
    root = root.expanduser().resolve()
    key = _key(root)
    now = time.monotonic()
    with _LOCK:
        cached = _SOURCE_CACHE.get(key)
        if cached and not force and now - cached[0] <= max(0.0, float(ttl)):
            return dict(cached[1])

    declared = _declared_github(root)
    binary = git_binary()
    ready = bool(binary) and (root / ".git").exists()
    result: dict[str, Any] = {
        "schema": "forge.source.status.fast.v1",
        "version": STATUS_CACHE_VERSION,
        "gitReady": ready,
        "gitBinary": binary,
        "hasHead": False,
        "branch": "",
        "head": "",
        "headShort": "",
        "clean": False,
        "staged": 0,
        "unstaged": 0,
        "untracked": 0,
        "untrackedApproximate": True,
        "ahead": None,
        "behind": None,
        "upstream": "",
        "remotes": [],
        "githubConfigured": False,
        "forgeGitConfigured": False,
        "internalGitConfigured": False,
        "forgejoConfigured": False,
        "githubDeclared": bool(declared.get("cloneUrl")),
        "githubDeclaredUrl": str(declared.get("cloneUrl") or ""),
        "githubDeclaredWebUrl": str(declared.get("webUrl") or ""),
    }
    if ready:
        try:
            cp = _run_git(root, ["status", "--porcelain=v2", "--branch", "--untracked-files=normal"], timeout=20)
            if cp.returncode == 0:
                result.update(_parse_porcelain_v2(cp.stdout))
            else:
                result["error"] = cp.stdout.strip() or f"git status exited {cp.returncode}"

            rem = _run_git(root, ["remote", "-v"], timeout=10)
            rows: list[dict[str, str]] = []
            seen: set[tuple[str, str, str]] = set()
            pattern = re.compile(r"^(\S+)\s+(\S+)\s+\((fetch|push)\)$")
            if rem.returncode == 0:
                for line in rem.stdout.splitlines():
                    match = pattern.match(line.strip())
                    if not match:
                        continue
                    name, url, direction = match.groups()
                    item = (name, url, direction)
                    if item in seen:
                        continue
                    seen.add(item)
                    rows.append({"name": name, "url": url, "direction": direction, "kind": _remote_kind(name, url)})
            result["remotes"] = rows
            result["githubConfigured"] = any(x["kind"] == "github" for x in rows)
            result["forgeGitConfigured"] = any(x["kind"] == "forgegit" for x in rows)
            result["internalGitConfigured"] = result["forgeGitConfigured"]
            result["forgejoConfigured"] = any(x["kind"] == "forgejo" for x in rows)
        except Exception as exc:
            result["error"] = str(exc)

    with _LOCK:
        _SOURCE_CACHE[key] = (now, dict(result))
    return result


def _fast_green(root: Path, source: dict[str, Any]) -> tuple[bool, bool, str]:
    """Conservative GREEN check for routine UI.

    Exact governed-source fingerprint verification remains at certification/source
    mutation boundaries. A compact UI GREEN match requires a clean tree at exactly
    the commit certified by the Full Gate.
    """
    try:
        from ForgeGreen import marker_path, read_green
        path = marker_path(root)
        data = read_green(root)
    except Exception:
        return False, False, ""
    if not data:
        return False, False, str(path)
    result = str(data.get("result") or data.get("status") or "").upper()
    marker = result in {"PASS", "GREEN", "OK", "SUCCESS"}
    if not marker:
        return False, False, str(path)
    gate_head = str(data.get("gitHeadAtGate") or "").strip()
    current_head = str(source.get("head") or "").strip()
    match = bool(source.get("clean") and gate_head and current_head and gate_head == current_head)
    return marker, match, str(path)


def fast_auto_status_payload(root: Path, *, ttl: float = 3.0, force: bool = False) -> dict[str, Any]:
    root = root.expanduser().resolve()
    key = _key(root)
    now = time.monotonic()
    with _LOCK:
        cached = _AUTO_CACHE.get(key)
        if cached and not force and now - cached[0] <= max(0.0, float(ttl)):
            return dict(cached[1])

    import PCCAutoAdapter as adapter
    from PCCProjectDiscovery import discover_project_contract_data

    data = discover_project_contract_data(root)
    source = fast_source_status(root, ttl=ttl, force=force)
    git = {
        "gitReady": source.get("gitReady", False),
        "clean": source.get("clean", False),
        "staged": source.get("staged", 0),
        "unstaged": source.get("unstaged", 0),
        "untracked": source.get("untracked", 0),
        "branch": source.get("branch", ""),
        "headShort": source.get("headShort", ""),
        "ahead": source.get("ahead"),
        "behind": source.get("behind"),
    }
    marker, match, marker_path = _fast_green(root, source)
    git["greenMarker"] = marker
    git["greenMatch"] = match
    git["greenMarkerPath"] = marker_path
    pending, invalid = adapter._count_updates(root, data)
    tools, toolchain = adapter._toolchain(root)
    discovery = data.get("_pccDiscovery") or {}
    payload = {
        "schema": "forge.auto_status.fast.v1",
        "adapter": {
            "version": getattr(adapter, "AUTO_ADAPTER_VERSION", ""),
            "source": discovery.get("source"),
            "provider": discovery.get("provider"),
        },
        "git": git,
        "sourceControl": source,
        "patches": {"pending": pending, "invalid": invalid},
        "hygiene": adapter._hygiene(root),
        "binaries": {"gui": "Registered runtime command" if adapter._has_run_command(data) else ""},
        "tools": tools,
        "toolchain": toolchain,
        "session": {"log": adapter._latest_session_log(root)},
        "fastUiStatus": True,
    }
    with _LOCK:
        _AUTO_CACHE[key] = (now, dict(payload))
    return payload


def patch_runtime_modules() -> None:
    """Route routine generic/ForgePY-adapter status through the bounded cache."""
    try:
        import PCCAutoAdapter
        PCCAutoAdapter.status_payload = fast_auto_status_payload
        PCCAutoAdapter.forgepy_source_status = fast_source_status
    except Exception:
        pass
    try:
        import ForgeHealth
        ForgeHealth.status_payload = fast_auto_status_payload
    except Exception:
        pass
    try:
        import ForgeGeneratedAdapterProvider
        ForgeGeneratedAdapterProvider.status_payload = fast_auto_status_payload
    except Exception:
        pass
    try:
        import ForgeGui
        ForgeGui.forgepy_source_status = fast_source_status
    except Exception:
        pass


def patch_simplified_ux(module: Any) -> None:
    """Make compact status asynchronous and root/generation safe."""
    if getattr(module, "_forge_fast_status_f562", False):
        return
    module._forge_fast_status_f562 = True

    def refresh_compact_status(gui: Any) -> None:
        root = Path(gui.root_path).expanduser().resolve()
        root_key = _key(root)
        running_key = str(getattr(gui, "_forge_compact_status_running_root", "") or "")
        if getattr(gui, "_forge_compact_status_running", False) and running_key == root_key:
            return

        generation = int(getattr(gui, "_forge_compact_status_generation", 0) or 0) + 1
        gui._forge_compact_status_generation = generation
        gui._forge_compact_status_running = True
        gui._forge_compact_status_running_root = root_key
        if not hasattr(gui, "_forge_compact_status_results"):
            gui._forge_compact_status_results = {}

        def worker() -> None:
            try:
                status = fast_source_status(root)
                identity = dict(module._project_identity(root) or {})
                bundle = module._latest_debug(root)
                result = (True, status, identity, bundle, "")
            except Exception as exc:
                result = (False, {}, {}, None, str(exc))
            gui._forge_compact_status_results[(generation, root_key)] = result

        def poll(attempts: int = 200) -> None:
            token = (generation, root_key)
            result = getattr(gui, "_forge_compact_status_results", {}).pop(token, None)
            current_root_key = _key(Path(gui.root_path))
            if current_root_key != root_key:
                if getattr(gui, "_forge_compact_status_running_root", "") == root_key:
                    gui._forge_compact_status_running = False
                    gui._forge_compact_status_running_root = ""
                # The old project result can never update the new project UI.
                try:
                    gui.window.after(0, lambda: refresh_compact_status(gui))
                except Exception:
                    pass
                return
            if result is None:
                if attempts > 0:
                    gui.window.after(25, lambda: poll(attempts - 1))
                else:
                    if getattr(gui, "_forge_compact_status_running_root", "") == root_key:
                        gui._forge_compact_status_running = False
                        gui._forge_compact_status_running_root = ""
                return

            if getattr(gui, "_forge_compact_status_running_root", "") == root_key:
                gui._forge_compact_status_running = False
                gui._forge_compact_status_running_root = ""
            ok, status, identity, bundle, _error = result
            if not ok:
                return
            branch = str(status.get("branch") or "-")
            clean = "CLEAN" if status.get("clean") else "DIRTY"
            remote = (
                "SYNC"
                if status.get("githubConfigured")
                and status.get("ahead") in {None, 0}
                and status.get("behind") in {None, 0}
                else ("GITHUB" if status.get("githubConfigured") else "LOCAL")
            )
            name = str(getattr(getattr(gui, "contract", None), "name", "") or root.name)
            build = str(
                identity.get("projectBuild")
                or identity.get("greenId")
                or identity.get("projectVersion")
                or ""
            ).strip()
            label = f"{name}  ·  {build}" if build else name
            try:
                gui._forge_status_project.configure(text=label)
                gui._forge_status_git.configure(text=f"{branch} · {clean} · {remote}")
                if hasattr(gui, "_forge_quick_project"):
                    gui._forge_quick_project.configure(text=label)
                gui._forge_health_project.configure(text=name)
                gui._forge_health_build.configure(text=build or "No declared build")
                gui._forge_debug_button.configure(state="normal" if bundle else "disabled")
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name="ForgeCompactStatus").start()
        try:
            gui.window.after(25, poll)
        except Exception:
            gui._forge_compact_status_running = False
            gui._forge_compact_status_running_root = ""

    module._refresh_compact_status = refresh_compact_status
    try:
        module._source_status = fast_source_status
    except Exception:
        pass
