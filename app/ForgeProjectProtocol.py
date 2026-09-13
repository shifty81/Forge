#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

PROTOCOL_VERSION = "FORGEPY-PROJECT-PROTOCOL-1.3-F620"


@dataclass(frozen=True)
class CapabilitySpec:
    key: str
    label: str
    category: str
    required_level: str = "optional"
    owner: str = "project"  # project | forgepy | either
    risk: str = "read"
    mutates: bool = False
    description: str = ""
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Project-owned capabilities describe what the repository itself must expose so it
# remains independently operable without ForgePY. ForgePY-owned capabilities are
# universal services and must not be falsely reported as missing from every project.
SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec("project.status", "Project Status", "Project", "standard", "project", description="Machine-readable project status.", aliases=("status-json", "status", "project-status")),
    CapabilitySpec("project.health", "Project Health", "Project", "standard", "project", description="Toolchain/project health diagnostics.", aliases=("doctor", "health")),
    CapabilitySpec("project.audit", "Project Audit", "Project", "certified", "forgepy", description="ForgePY integration/project audit."),
    CapabilitySpec("project.self-test", "Project Self Test", "Project", "standard", "project", description="Control-center/provider self-test.", aliases=("self-test",)),
    CapabilitySpec("gate.full", "Full Quality Gate", "Certification", "standard", "project", risk="write", mutates=True, description="Authoritative certification gate.", aliases=("full", "full-gate", "gate.full", "build.full", "quality.full")),
    CapabilitySpec("gate.fast", "Fast Gate", "Certification", "optional", "project", description="Non-authoritative fast validation.", aliases=("fast", "quick", "fast-gate", "gate.quick", "build.fast", "build.quick")),
    CapabilitySpec("build.default", "Build", "Build & Test", "standard", "project", risk="write", mutates=True, aliases=("build", "build.native", "build.debug", "build.render")),
    CapabilitySpec("build.release", "Release Build", "Build & Test", "optional", "project", risk="write", mutates=True, aliases=("build-release",)),
    CapabilitySpec("test.default", "Test", "Build & Test", "certified", "project", aliases=("test", "test.native")),
    CapabilitySpec("run.default", "Run", "Run", "standard", "project", aliases=("run", "launch-gui", "run.game", "run.client", "run.runtime")),
    CapabilitySpec("run.editor", "Run Editor", "Run", "optional", "project", aliases=("run-editor", "run.editor")),
    CapabilitySpec("run.server", "Run Server", "Run", "optional", "project", aliases=("run-server", "run.server")),

    CapabilitySpec("patch.status", "Patch Status", "Updates", "standard", "forgepy", aliases=("patch-status", "patch.preview")),
    CapabilitySpec("patch.queue", "Queue Patch", "Updates", "standard", "forgepy", risk="write", mutates=True, description="Validate and queue a transport without modifying project source."),
    CapabilitySpec("patch.review", "Review Updates", "Updates", "standard", "forgepy"),
    CapabilitySpec("patch.apply-staged", "Apply Staged Updates", "Updates", "standard", "forgepy", risk="confirm", mutates=True, aliases=("patch-apply", "patch.apply")),
    CapabilitySpec("patch.unstage", "Unstage Update", "Updates", "optional", "forgepy", risk="write", mutates=True),

    CapabilitySpec("source.status", "Source Status", "Source & Recovery", "standard", "forgepy", aliases=("git-status", "git.status")),
    CapabilitySpec("source.history", "Source History", "Source & Recovery", "optional", "forgepy", aliases=("git-history", "git.history")),
    CapabilitySpec("source.commit-green", "Commit GREEN", "Source & Recovery", "standard", "forgepy", risk="write", mutates=True, aliases=("commit-green", "git.commit-green")),
    CapabilitySpec("source.push", "Push", "Source & Recovery", "standard", "forgepy", risk="write", mutates=True, aliases=("push", "git-push", "git.push")),
    CapabilitySpec("source.pull", "Pull", "Source & Recovery", "optional", "forgepy", risk="write", mutates=True, aliases=("git-pull", "git.pull")),

    CapabilitySpec("diagnostics.bundle", "Debug Bundle", "Diagnostics", "standard", "project", risk="write", mutates=True, aliases=("debug-bundle",)),
    CapabilitySpec("diagnostics.logs", "Logs", "Diagnostics", "standard", "forgepy"),
    CapabilitySpec("diagnostics.latest", "Latest Diagnostics", "Diagnostics", "optional", "forgepy", aliases=("open-latest-debug",)),
    CapabilitySpec("artifacts.list", "Artifacts", "Artifacts", "standard", "forgepy"),
    CapabilitySpec("recovery.status", "Recovery Status", "Source & Recovery", "certified", "forgepy"),
    CapabilitySpec("recovery.restore", "Restore Recovery Point", "Source & Recovery", "certified", "forgepy", risk="confirm", mutates=True),
)

_BY_KEY = {spec.key.casefold(): spec for spec in SPECS}
_ALIAS_TO_KEY: dict[str, str] = {}
_ALIAS_CONFLICTS: dict[str, set[str]] = {}
for _spec in SPECS:
    for _alias in (_spec.key, *_spec.aliases):
        folded = _alias.casefold()
        existing = _ALIAS_TO_KEY.get(folded)
        if existing and existing != _spec.key:
            _ALIAS_CONFLICTS.setdefault(folded, {existing}).add(_spec.key)
        else:
            _ALIAS_TO_KEY[folded] = _spec.key


def protocol_conflicts() -> dict[str, list[str]]:
    return {key: sorted(values) for key, values in _ALIAS_CONFLICTS.items()}


def normalize_key(key: str) -> str:
    raw = str(key or "").strip()
    return _ALIAS_TO_KEY.get(raw.casefold(), raw)


def aliases_for(key: str) -> tuple[str, ...]:
    canonical = normalize_key(key)
    spec = _BY_KEY.get(canonical.casefold())
    return spec.aliases if spec else ()


def spec_for(key: str) -> CapabilitySpec | None:
    return _BY_KEY.get(normalize_key(key).casefold())

PROVIDER_COMMANDS: dict[str, str] = {
    "gate.full": "full",
    "gate.fast": "fast",
    "build.default": "build",
    "build.release": "build-release",
    "test.default": "test",
    "run.default": "launch-gui",
    "run.editor": "run-editor",
    "run.server": "run-server",
    "project.health": "doctor",
    "project.self-test": "self-test",
    "patch.apply-staged": "patch-apply",
    "source.history": "git-history",
    "source.commit-green": "commit-green",
    "source.push": "push",
    "source.pull": "git-pull",
    "diagnostics.bundle": "debug-bundle",
}


def provider_command(key: str) -> str:
    """Return the legacy/provider command used behind one canonical ForgePY key."""
    canonical = normalize_key(key)
    return PROVIDER_COMMANDS.get(canonical, str(key))


def canonicalize(keys: Iterable[str]) -> set[str]:
    return {normalize_key(str(key)) for key in keys if str(key or "").strip()}


def forgepy_capabilities() -> set[str]:
    return {spec.key for spec in SPECS if spec.owner == "forgepy"}


def effective_capabilities(project_commands: Iterable[str], extra_capabilities: Iterable[str] = ()) -> set[str]:
    return canonicalize((*tuple(project_commands), *tuple(extra_capabilities))) | forgepy_capabilities()


def matrix(project_commands: Iterable[str], extra_capabilities: Iterable[str] = ()) -> list[dict[str, Any]]:
    raw = {str(value).strip() for value in project_commands if str(value).strip()}
    project = canonicalize(raw)
    extras = canonicalize(extra_capabilities)
    effective = project | extras | forgepy_capabilities()
    rows: list[dict[str, Any]] = []
    for spec in SPECS:
        rows.append({
            **spec.to_dict(),
            "available": spec.key in effective,
            "projectProvided": spec.key in project,
            "forgePyProvided": spec.key in forgepy_capabilities(),
            "matchedBy": sorted(value for value in raw if normalize_key(value) == spec.key),
        })
    return rows


def _project_required(levels: set[str]) -> set[str]:
    return {
        spec.key for spec in SPECS
        if spec.required_level in levels and spec.owner == "project"
    }


def integration_grade(
    project_commands: Iterable[str],
    *,
    audit_current: bool = False,
    handoffs_current: bool = False,
) -> dict[str, Any]:
    project = canonicalize(project_commands)
    effective = project | forgepy_capabilities()
    standard_required = _project_required({"standard"})
    certified_required = _project_required({"standard", "certified"})
    standard_missing = sorted(standard_required - project)
    certified_missing = sorted(certified_required - project)

    if not project:
        grade = "DISCOVERED"
    elif not audit_current:
        grade = "AUDITING"
    elif standard_missing:
        grade = "ADAPTED"
    elif certified_missing or not handoffs_current:
        grade = "STANDARDIZED"
    else:
        grade = "CERTIFIED"

    legacy = {
        "DISCOVERED": "OBSERVED",
        "AUDITING": "ADAPTED",
        "ADAPTED": "ADAPTED",
        "STANDARDIZED": "STANDARD",
        "CERTIFIED": "CERTIFIED",
    }[grade]
    return {
        "schema": "forgepy.project-protocol-grade.v2",
        "version": PROTOCOL_VERSION,
        "grade": grade,
        "legacyGrade": legacy,
        "projectCapabilities": sorted(project),
        "forgePyCapabilities": sorted(forgepy_capabilities()),
        "effectiveCapabilities": sorted(effective),
        # compatibility field: historically this meant project capabilities.
        "capabilities": sorted(project),
        "standardMissing": standard_missing,
        "certifiedMissing": certified_missing,
        "auditCurrent": bool(audit_current),
        "handoffsCurrent": bool(handoffs_current),
    }
