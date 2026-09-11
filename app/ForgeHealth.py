#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PCCAutoAdapter import status_payload
from PCCSurfaceCommon import BackendClient, ProjectContract, SurfaceError

FORGE_HEALTH_VERSION = "FORGEPY-HEALTH-0.4.17"
VAULT_HEALTH_VERSION = FORGE_HEALTH_VERSION


@dataclass(frozen=True)
class ProjectHealth:
    level: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    status: dict[str, Any] = field(default_factory=dict, compare=False)
    provider: str = ""
    score: int = 0
    components: dict[str, dict[str, Any]] = field(default_factory=dict, compare=False)

    @property
    def label(self) -> str:
        if not self.reasons:
            return self.level
        return f"{self.level} — {self.reasons[0]}"


def _push(bucket: list[str], message: str) -> None:
    if message and message not in bucket:
        bucket.append(message)


def evaluate_project(root: Path, contract: ProjectContract | None = None) -> ProjectHealth:
    root = root.expanduser().resolve()
    failures: list[str] = []
    warnings: list[str] = []
    provider = ""

    if not root.is_dir():
        return ProjectHealth("FAIL", ("project root missing",), {}, "", 0, {"Root": {"status": "FAIL", "weight": 100}})

    try:
        contract = contract or ProjectContract.load(root)
    except Exception as exc:
        return ProjectHealth("FAIL", (f"project discovery failed: {exc}",), {}, "", 0, {"Discovery": {"status": "FAIL", "weight": 100}})

    try:
        backend = BackendClient(root, contract)
        provider = backend.provider_label
    except SurfaceError as exc:
        _push(failures, f"ForgePY provider unavailable: {exc}")
    except Exception as exc:
        _push(failures, f"ForgePY provider invalid: {exc}")

    try:
        status = status_payload(root)
    except Exception as exc:
        return ProjectHealth("FAIL", tuple(failures + [f"health scan failed: {exc}"]), {}, provider, 0, {"Scan": {"status": "FAIL", "weight": 100}})

    git = status.get("git") or {}
    patches = status.get("patches") or {}
    hygiene = status.get("hygiene") or {}
    tools = status.get("tools") or {}
    source_control = status.get("sourceControl") or {}

    # If this is a Git working tree, Git being unavailable is a hard operational failure.
    if (root / ".git").exists() and not git.get("gitReady"):
        _push(failures, "Git repository detected but Git is unavailable")
    elif git.get("gitReady"):
        if not git.get("clean"):
            changed = int(git.get("staged", 0) or 0) + int(git.get("unstaged", 0) or 0) + int(git.get("untracked", 0) or 0)
            _push(warnings, f"source modified ({changed})" if changed else "source modified")
        if git.get("greenMarker") and not git.get("greenMatch"):
            _push(warnings, "certified GREEN is stale")
        elif not git.get("greenMarker"):
            _push(warnings, "no certified GREEN marker")
        ahead = git.get("ahead")
        behind = git.get("behind")
        if behind not in (None, 0):
            _push(warnings, f"remote behind/ahead mismatch ({ahead or 0}↑ {behind}↓)")
        elif ahead not in (None, 0):
            _push(warnings, f"local branch ahead by {ahead}")

    invalid = int(patches.get("invalid", 0) or 0)
    pending = int(patches.get("pending", 0) or 0)
    if invalid:
        _push(failures, f"{invalid} invalid patch(es)")
    if pending:
        _push(warnings, f"{pending} pending update(s)")

    if not hygiene.get("clean", True):
        _push(warnings, f"repository hygiene has {hygiene.get('violationCount', '?')} issue(s)")

    missing_tools = [name for name, ready in tools.items() if ready is False]
    if missing_tools:
        _push(failures, "required toolchain missing: " + ", ".join(sorted(missing_tools)))

    # GitHub and ForgeGit are the primary source-control authorities.
    # Forgejo remains optional compatibility/source-hosting infrastructure.
    if git.get("gitReady"):
        if not source_control.get("githubConfigured"):
            _push(warnings, "GitHub remote not configured")
        if not (source_control.get("forgeGitConfigured") or source_control.get("internalGitConfigured")):
            _push(warnings, "ForgeGit not configured")

    components: dict[str, dict[str, Any]] = {}
    def component(name: str, weight: int, state: str, detail: str = "") -> None:
        factor = 1.0 if state == "PASS" else (0.5 if state == "WARN" else 0.0)
        components[name] = {"status": state, "weight": weight, "points": round(weight * factor), "detail": detail}

    component("Provider", 15, "PASS" if provider and not any("provider" in x.casefold() for x in failures) else "FAIL", provider or "unavailable")
    if git.get("gitReady"):
        component("Git", 15, "PASS", str(git.get("branch") or "ready"))
        component("GREEN", 20, "PASS" if git.get("greenMarker") and git.get("greenMatch") else ("WARN" if git.get("greenMarker") else "WARN"), "certified source")
        ahead, behind = git.get("ahead"), git.get("behind")
        sync_state = "PASS" if ahead == 0 and behind == 0 else ("WARN" if ahead is None or behind is None or (behind in (0, None)) else "FAIL")
        component("Sync", 10, sync_state, f"{ahead} ahead / {behind} behind")
    else:
        # Non-Git projects can still be operational, but source-control normalization remains visible.
        component("Git", 15, "WARN" if not (root / ".git").exists() else "FAIL", "not initialized" if not (root / ".git").exists() else "unavailable")
        component("GREEN", 20, "WARN", "no Git-backed certification")
        component("Sync", 10, "WARN", "not configured")
    component("Updates", 15, "FAIL" if invalid else ("WARN" if pending else "PASS"), f"{pending} pending / {invalid} invalid")
    component("Hygiene", 10, "PASS" if hygiene.get("clean", True) else "WARN", f"{hygiene.get('violationCount', 0)} issue(s)")
    component("Tooling", 15, "FAIL" if missing_tools else "PASS", "missing: " + ", ".join(missing_tools) if missing_tools else "ready")
    score = max(0, min(100, sum(int(row.get("points", 0)) for row in components.values())))
    level = "FAIL" if failures else ("WARN" if warnings else "GREEN")
    reasons = tuple(failures + warnings)
    return ProjectHealth(level, reasons, status, provider, score, components)
