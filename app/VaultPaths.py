#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

from VaultSettings import load_settings


def _configured_path(*names: str) -> Path | None:
    for name in names:
        raw = str(os.environ.get(name) or "").strip()
        if raw:
            return Path(raw).expanduser().resolve()
    return None


def data_root() -> Path:
    override = _configured_path("FORGEPY_DATA_ROOT", "FORGE_DATA_ROOT", "VAULT_DATA_ROOT")
    if override is not None:
        return override
    settings = load_settings()
    raw = str(settings.get("vaultHome") or "").strip()
    if raw:
        return Path(raw).expanduser()
    if os.name == "nt":
        d_drive = Path("D:/")
        if d_drive.exists():
            return d_drive / "Vault"
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "ForgePY"
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "forgepy"


def registry_path() -> Path:
    override = _configured_path("FORGEPY_PROJECT_REGISTRY", "FORGE_PROJECT_REGISTRY", "VAULT_PROJECT_REGISTRY")
    if override is not None:
        return override
    return data_root() / "project_registry.json"


def projects_root() -> Path:
    override = _configured_path("FORGEPY_PROJECTS_ROOT", "FORGE_PROJECTS_ROOT", "VAULT_PROJECTS_ROOT")
    if override is not None:
        return override
    raw = str(load_settings().get("projectsRoot") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return data_root() / "Projects"


def configured_scan_roots() -> tuple[Path, ...]:
    raw_env = str(os.environ.get("FORGEPY_SCAN_ROOTS") or os.environ.get("FORGE_SCAN_ROOTS") or os.environ.get("VAULT_SCAN_ROOTS") or "").strip()
    if raw_env:
        return _unique_paths(Path(x.strip()).expanduser() for x in raw_env.split(os.pathsep) if x.strip())
    settings = load_settings()
    values = settings.get("scanRoots") or []
    roots = [Path(str(x)).expanduser() for x in values if str(x).strip()]
    if not roots:
        roots = [projects_root()]
    return _unique_paths(roots)


def legacy_registry_paths() -> tuple[Path, ...]:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return (
            base / "Forge" / "project_registry.json",
            base / "ProjectControlCenter" / "project_registry.json",
        )
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return (
        data / "forge" / "project_registry.json",
        config / "project-control-center" / "project_registry.json",
    )


def legacy_registry_path() -> Path:
    return legacy_registry_paths()[0]


def vault_root() -> Path:
    override = _configured_path("FORGEPY_VAULT_ROOT", "FORGE_VAULT_ROOT", "VAULT_STORAGE_ROOT", "VAULT_VAULT_ROOT", "PCC_VAULT_ROOT")
    if override is not None:
        return override
    return data_root() / "Library"



def artifact_central_root() -> Path:
    override = _configured_path("FORGEPY_ARTIFACT_CENTRAL_ROOT", "FORGE_ARTIFACT_CENTRAL_ROOT", "VAULT_ARTIFACT_CENTRAL_ROOT")
    if override is not None:
        return override
    raw = str(load_settings().get("artifactCentralRoot") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return data_root() / "ArtifactCentral"


def project_artifact_root(project_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in str(project_id)).strip("-.") or "unassigned"
    return artifact_central_root() / "projects" / safe


def ensure_artifact_project_tree(project_id: str) -> dict[str, Path]:
    base = project_artifact_root(project_id)
    mapping = {
        "root": base,
        "patches": base / "patches",
        "debug-bundles": base / "debug-bundles",
        "source-rollups": base / "source-rollups",
        "builds": base / "builds",
        "releases": base / "releases",
        "baselines": base / "baselines",
        "logs": base / "logs",
        "reports": base / "reports",
        "asset-intake": base / "asset-intake",
        "backups": base / "backups",
        "review": base / "review",
    }
    ensure_dirs(mapping.values())
    return mapping

def downloads_roots() -> tuple[Path, ...]:
    raw = str(os.environ.get("FORGEPY_INTAKE_PATHS") or os.environ.get("FORGE_INTAKE_PATHS") or os.environ.get("VAULT_INTAKE_PATHS") or "").strip()
    candidates: list[Path] = []
    if raw:
        for item in raw.split(os.pathsep):
            item = item.strip()
            if item:
                candidates.append(Path(item).expanduser())
    else:
        candidates.append(Path.home() / "Downloads")
    return _unique_paths(candidates)


def intake_roots(extra_roots: Sequence[Path] = ()) -> tuple[Path, ...]:
    candidates: list[Path] = [*downloads_roots(), *extra_roots]
    return _unique_paths(candidates)


def _unique_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            normalized = os.path.normcase(str(path.expanduser().resolve()))
        except Exception:
            normalized = os.path.normcase(str(path.expanduser()))
        if normalized not in seen:
            seen.add(normalized)
            unique.append(path.expanduser())
    return tuple(unique)


def ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
