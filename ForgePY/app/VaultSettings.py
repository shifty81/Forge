#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

SETTINGS_VERSION = "FORGEPY-SETTINGS-0.4.17"
APP_ROOT = Path(__file__).resolve().parents[1]


def _windows_d_drive() -> Path | None:
    if os.name == "nt":
        d = Path("D:/")
        if d.exists():
            return d
    return None


def _local_settings_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        preferred = base / "ForgePY" / "bootstrap.settings.json"
        forge_legacy = base / "Forge" / "bootstrap.settings.json"
        vault_legacy = base / "Vault" / "bootstrap.settings.json"
        if preferred.is_file(): return preferred
        if forge_legacy.is_file(): return forge_legacy
        if vault_legacy.is_file(): return vault_legacy
        return preferred
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    preferred = base / "forgepy" / "bootstrap.settings.json"
    forge_legacy = base / "forge" / "bootstrap.settings.json"
    vault_legacy = base / "vault" / "bootstrap.settings.json"
    if preferred.is_file(): return preferred
    if forge_legacy.is_file(): return forge_legacy
    if vault_legacy.is_file(): return vault_legacy
    return preferred


def portable_settings_path() -> Path:
    preferred = APP_ROOT / "forgepy.settings.json"
    forge_legacy = APP_ROOT / "forge.settings.json"
    vault_legacy = APP_ROOT / "vault.settings.json"
    if preferred.is_file(): return preferred
    if forge_legacy.is_file(): return forge_legacy
    if vault_legacy.is_file(): return vault_legacy
    return preferred


def settings_path() -> Path:
    override = str(os.environ.get("FORGEPY_SETTINGS_PATH") or os.environ.get("FORGE_SETTINGS_PATH") or os.environ.get("VAULT_SETTINGS_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    portable = portable_settings_path()
    if portable.is_file():
        return portable
    return _local_settings_path()


def defaults() -> dict[str, Any]:
    d = _windows_d_drive()
    if d is not None:
        preferred = d / "ForgePY"
        forge_legacy = d / "Forge"
        vault_legacy = d / "Vault"
        # Existing Forge/Vault data remains authoritative until the user explicitly migrates it.
        if preferred.exists():
            home = preferred
        elif forge_legacy.exists():
            home = forge_legacy
        elif vault_legacy.exists():
            home = vault_legacy
        else:
            home = preferred
        projects = d / "Projects"
        scans = [str(d)]
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        preferred = base / "ForgePY"
        forge_legacy = base / "Forge"
        vault_legacy = base / "Vault"
        if preferred.exists():
            home = preferred
        elif forge_legacy.exists():
            home = forge_legacy
        elif vault_legacy.exists():
            home = vault_legacy
        else:
            home = preferred
        projects = Path.home() / "Projects"
        scans = [str(projects)]
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        preferred = base / "forgepy"
        forge_legacy = base / "forge"
        vault_legacy = base / "vault"
        if preferred.exists():
            home = preferred
        elif forge_legacy.exists():
            home = forge_legacy
        elif vault_legacy.exists():
            home = vault_legacy
        else:
            home = preferred
        projects = Path.home() / "Projects"
        scans = [str(projects)]

    artifact_root = home / "ArtifactCentral"
    return {
        "schema": "forgepy.settings.v1",
        "version": SETTINGS_VERSION,
        "vaultHome": str(home),
        "projectsRoot": str(projects),
        "scanRoots": scans,
        "artifactCentralRoot": str(artifact_root),
        "portable": settings_path() == portable_settings_path(),
        "ui": {
            "closeToTray": True,
            "minimizeToTray": True,
            "startMinimized": False,
            "showTrayNotifications": True,
            "leftRailCollapsed": False,
            "healthRailCollapsed": False,
            "healthRefreshSeconds": 30,
        },
        "services": {
            "intakeWatcher": True,
            "driveWatcher": False,
            "forgejoAutoStart": False,
            "cortexAutoStart": False,
        },
        "intake": {
            "enabled": True,
            "pollSeconds": 8,
            "watchDownloads": True,
            "watchProjectRoot": True,
            "stabilitySeconds": 2.0,
            "coldStableSeconds": 10.0,
            "packageClockToleranceHours": 48,
            "futureClockToleranceMinutes": 10,
            "requirePackageDate": False,
            "requireBuildIdentityWhenDeclared": True,
            "archiveNonPatchArtifacts": True,
            "maxPatchFiles": 5000,
            "maxPatchUncompressedBytes": 2147483648,
            "maxPatchSingleFileBytes": 536870912,
        },
        "forgejo": {
            "url": "http://127.0.0.1:3000",
            "workPath": str(home / "Forgejo"),
            "binary": "",
            "config": str(home / "Forgejo" / "custom" / "conf" / "app.ini"),
        },
        "sourceControl": {
            "gitBinary": "",
            "githubCliBinary": "",
            "defaultGitHubRemote": "origin",
            "internalGitEnabled": True,
            "internalGitRoot": str(home / "InternalGit"),
            "defaultInternalGitRemote": "forgepy-internal",
            "defaultForgejoRemote": "forgejo",
            "fetchOnStatus": False,
        },
        "ide": {
            "enabled": True,
            "host": "pywebview",
            "pywebviewVersion": "6.2.1",
            "monacoVersion": "0.56.0",
            "monacoRoot": str(home / "Components" / "Monaco"),
            "fontSize": 13,
            "wordWrap": "off",
            "minimap": True,
            "autosave": False,
            "autosaveDelayMs": 1500,
            "windowWidth": 1500,
            "windowHeight": 920,
            "devTools": False,
        },
        "cortex": {
            "projectRoot": "",
            "executable": "",
            "arguments": [],
            "serviceUrl": "",
            "healthPath": "",
        },
        "tooling": {
            "extraSearchPaths": [],
            "deepScanRegisteredProjects": True,
            "includeArchivedTooling": False,
            "preferredBlenderBinary": "",
            "preferredPythonBinary": "",
            "preferredCMakeBinary": "",
            "preferredMSBuildBinary": "",
        },
        "security": {
            "strictModernPatches": True,
            "legacyPatchPolicy": "review",
            "requireModernBuildBinding": True,
            "allowUnsignedLocalPatches": True,
            "blenderDisableAutoexec": True,
        },
    }


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(dict(out[key]), value)
        else:
            out[key] = value
    return out


def load_settings() -> dict[str, Any]:
    base = defaults()
    path = settings_path()
    if not path.is_file():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return base
    if not isinstance(raw, dict):
        return base
    merged = _merge(base, raw)
    # Legacy Forge/Vault settings remain readable, but the in-memory authority is
    # always normalized to the current ForgePY schema/version. This prevents an
    # old saved schema marker from leaking back into newly written settings.
    merged["schema"] = "forgepy.settings.v1"
    merged["version"] = SETTINGS_VERSION
    merged["portable"] = path == portable_settings_path()
    return merged


def _atomic_write(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
    return path


def save_settings(data: dict[str, Any], *, portable: bool | None = None) -> Path:
    target = settings_path()
    if portable is True:
        target = portable_settings_path()
    elif portable is False:
        target = _local_settings_path()
    payload = _merge(defaults(), data)
    payload["schema"] = "forgepy.settings.v1"
    payload["version"] = SETTINGS_VERSION
    payload["portable"] = target == portable_settings_path()
    return _atomic_write(target, payload)


def update_settings(**changes: Any) -> tuple[dict[str, Any], Path]:
    data = load_settings()
    for key, value in changes.items():
        data[key] = value
    path = save_settings(data)
    return data, path


def set_section(section: str, values: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    data = load_settings()
    current = dict(data.get(section) or {})
    current.update(values)
    data[section] = current
    return data, save_settings(data)


def set_vault_home(path: Path) -> tuple[dict[str, Any], Path]:
    target = path.expanduser().resolve()
    data = load_settings()
    old_home = Path(str(data.get("vaultHome") or "")).expanduser()
    data["vaultHome"] = str(target)

    forgejo = dict(data.get("forgejo") or {})
    old_work = str(forgejo.get("workPath") or "")
    old_config = str(forgejo.get("config") or "")
    if not old_work or (old_home and Path(old_work) == old_home / "Forgejo"):
        forgejo["workPath"] = str(target / "Forgejo")
    if not old_config or (old_home and Path(old_config) == old_home / "Forgejo" / "custom" / "conf" / "app.ini"):
        forgejo["config"] = str(target / "Forgejo" / "custom" / "conf" / "app.ini")
    data["forgejo"] = forgejo

    old_artifacts = str(data.get("artifactCentralRoot") or "")
    if not old_artifacts or (old_home and Path(old_artifacts) == old_home / "ArtifactCentral"):
        data["artifactCentralRoot"] = str(target / "ArtifactCentral")

    ide = dict(data.get("ide") or {})
    old_monaco = str(ide.get("monacoRoot") or "")
    if not old_monaco or (old_home and Path(old_monaco) == old_home / "Components" / "Monaco"):
        ide["monacoRoot"] = str(target / "Components" / "Monaco")
    data["ide"] = ide

    return data, save_settings(data)


def set_projects_root(path: Path) -> tuple[dict[str, Any], Path]:
    data = load_settings()
    data["projectsRoot"] = str(path.expanduser().resolve())
    return data, save_settings(data)


def set_artifact_central_root(path: Path) -> tuple[dict[str, Any], Path]:
    data = load_settings()
    data["artifactCentralRoot"] = str(path.expanduser().resolve())
    return data, save_settings(data)


def set_scan_roots(paths: list[Path]) -> tuple[dict[str, Any], Path]:
    data = load_settings()
    unique: list[str] = []
    seen: set[str] = set()
    for path in paths:
        text = str(path.expanduser().resolve())
        key = os.path.normcase(text)
        if key not in seen:
            seen.add(key)
            unique.append(text)
    data["scanRoots"] = unique
    return data, save_settings(data)
