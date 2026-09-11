#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TOOLING_VERSION = "VAULT-TOOLING-0.4.1"
SCRIPT_EXTS = {
    ".py", ".ps1", ".psm1", ".psd1", ".cmd", ".bat", ".sh", ".bash", ".zsh",
    ".js", ".mjs", ".cjs", ".ts", ".lua", ".rb", ".pl", ".csx", ".groovy",
}
ROOT_TOOL_EXTS = SCRIPT_EXTS | {".exe"}
SKIP_DIRS = {".git", "target", "node_modules", ".venv", "venv", "build", "dist", "__pycache__", ".cache", ".idea", ".vs"}
TOOL_DIR_HINTS = {"tools", "scripts", "automation", "ci", "devtools", "build_tools", "tooling", "blender", "utilities", "utils"}

CLI_CANDIDATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("git", ("git",)), ("github", ("gh",)), ("forgejo", ("forgejo",)),
    ("python", ("python", "python3")), ("powershell", ("pwsh", "powershell")),
    ("cargo", ("cargo",)), ("rustc", ("rustc",)), ("cmake", ("cmake",)),
    ("ninja", ("ninja",)), ("msbuild", ("msbuild", "MSBuild.exe")),
    ("dotnet", ("dotnet",)), ("java", ("java",)), ("gradle", ("gradle", "gradlew")),
    ("node", ("node",)), ("npm", ("npm", "npm.cmd")), ("blender", ("blender", "blender.exe")),
    ("ffmpeg", ("ffmpeg",)), ("7zip", ("7z", "7zz")), ("sqlite", ("sqlite3",)),
    ("ripgrep", ("rg",)), ("docker", ("docker",)), ("cmake-gui", ("cmake-gui",)),
)

BUILD_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rust/cargo", ("Cargo.toml",)),
    ("cmake", ("CMakeLists.txt",)),
    ("visual-studio", ("*.sln", "*.vcxproj")),
    ("dotnet", ("*.csproj", "*.fsproj")),
    ("node", ("package.json",)),
    ("gradle", ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")),
    ("python", ("pyproject.toml", "setup.py", "requirements.txt")),
    ("godot", ("project.godot",)),
    ("unreal", ("*.uproject",)),
    ("blender", ("*.blend",)),
)


@dataclass(frozen=True)
class ToolRecord:
    path: str
    domain: str
    kind: str
    status: str = "active"
    source: str = "scan"


def _domain(path: Path) -> str:
    parts = [p.casefold().replace("_", "-") for p in path.parts]
    ordered = (
        ("blender", {"blender"}),
        ("source-control", {"git", "github", "forgejo", "source-control", "sourcecontrol"}),
        ("patch-updates", {"patch", "patches", "update", "updates", "repair", "repairs"}),
        ("validation", {"validation", "validators", "checks", "audit", "audits"}),
        ("build", {"build", "builds", "compile"}),
        ("packaging", {"packaging", "package", "release", "releases", "rollup", "rollups"}),
        ("assets", {"asset", "assets", "content"}),
        ("characters", {"character", "characters", "animation", "animations"}),
        ("terrain", {"terrain", "world", "worldgen"}),
        ("pcg", {"pcg", "pcg-pipeline", "generation"}),
        ("tests", {"test", "tests", "smoke", "certification"}),
        ("dependencies", {"dependency", "dependencies", "vendor"}),
        ("server-deploy", {"server", "servers", "deploy", "deployment", "steamcmd"}),
        ("editor", {"editor", "ide"}),
        ("control", {"control", "pcc", "project-control"}),
        ("automation", {"automation", "scripts"}),
    )
    for domain, needles in ordered:
        if any(part in needles for part in parts):
            return domain
    n = path.name.casefold()
    if "blender" in n: return "blender"
    if any(x in n for x in ("patch", "update", "repair")): return "patch-updates"
    if any(x in n for x in ("valid", "check", "audit", "verify", "doctor")): return "validation"
    if any(x in n for x in ("build", "compile", "cmake")): return "build"
    if any(x in n for x in ("pack", "rollup", "release", "bundle")): return "packaging"
    if any(x in n for x in ("git", "github", "forgejo")): return "source-control"
    if any(x in n for x in ("server", "deploy", "steamcmd")): return "server-deploy"
    return "tooling"


def read_declared_registry(root: Path) -> list[ToolRecord]:
    candidates = [root / "tools" / "tool_registry.json", root / "tool_registry.json"]
    out: list[ToolRecord] = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        for row in data.get("entries", []) if isinstance(data, dict) else []:
            if not isinstance(row, dict):
                continue
            rel = str(row.get("path") or "").strip()
            if not rel:
                continue
            out.append(ToolRecord(rel, str(row.get("domain") or _domain(Path(rel))), str(row.get("kind") or Path(rel).suffix.lstrip(".") or "file"), str(row.get("status") or "active"), "registry"))
    return out


def read_declared_commands(root: Path) -> list[dict[str, Any]]:
    path = root / "project.control.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for row in data.get("commands", []) if isinstance(data, dict) else []:
        if not isinstance(row, dict) or not row.get("key"):
            continue
        rows.append({
            "key": str(row.get("key")),
            "label": str(row.get("label") or row.get("key")),
            "category": str(row.get("category") or "project"),
            "program": str(row.get("program") or ""),
            "mutates": bool(row.get("mutates") or str(row.get("risk") or "").casefold() in {"write", "destructive"}),
        })
    return rows


def _tool_scan_roots(root: Path) -> list[Path]:
    out: list[Path] = []
    for child in root.iterdir() if root.is_dir() else []:
        if child.is_dir() and child.name.casefold() in TOOL_DIR_HINTS:
            out.append(child)
    # Common nested authoritative paths.
    for candidate in (root / "tools" / "automation", root / "tools" / "control", root / "tools" / "blender"):
        if candidate.is_dir() and candidate not in out:
            out.append(candidate)
    return out


def scan_scripts(root: Path, *, max_files: int = 20000, include_archived: bool = False) -> list[ToolRecord]:
    root = root.expanduser().resolve()
    declared = read_declared_registry(root)
    records: dict[str, ToolRecord] = {r.path.replace("\\", "/").casefold(): r for r in declared if include_archived or r.status.casefold() != "archived"}

    # Root launchers/control utilities are important even if the project has no tools/ tree.
    try:
        for p in root.iterdir():
            if not p.is_file() or p.suffix.casefold() not in ROOT_TOOL_EXTS:
                continue
            n = p.name.casefold()
            if not any(token in n for token in ("tool", "control", "build", "run", "launch", "bootstrap", "verify", "gate", "patch", "update", "server", "deploy", "forge", "vault")):
                continue
            rel = p.relative_to(root).as_posix(); records.setdefault(rel.casefold(), ToolRecord(rel, _domain(Path(rel)), p.suffix.lstrip(".").casefold() or "binary", source="root-scan"))
    except OSError:
        pass

    for top in _tool_scan_roots(root):
        for base, dirs, files in os.walk(top):
            dirs[:] = [d for d in dirs if d.casefold() not in SKIP_DIRS and (include_archived or "archive" not in d.casefold())]
            b = Path(base)
            for name in files:
                if len(records) >= max_files:
                    return sorted(records.values(), key=lambda r: (r.domain, r.path.casefold()))
                p = b / name
                if p.suffix.casefold() not in SCRIPT_EXTS:
                    continue
                rel = p.relative_to(root).as_posix(); key = rel.casefold()
                records.setdefault(key, ToolRecord(rel, _domain(Path(rel)), p.suffix.lstrip(".").casefold() or "script"))
    return sorted(records.values(), key=lambda r: (r.domain, r.path.casefold()))


def detect_build_systems(root: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for name, patterns in BUILD_MARKERS:
        matches: list[str] = []
        for pattern in patterns:
            for p in root.glob(pattern):
                if p.exists():
                    matches.append(p.relative_to(root).as_posix())
        if matches:
            found.append({"system": name, "markers": sorted(set(matches))})
    return found


def inventory_cli(extra_paths: Iterable[Path] = ()) -> dict[str, dict[str, Any]]:
    search_path = os.environ.get("PATH", "")
    if extra_paths:
        search_path = os.pathsep.join([*(str(p) for p in extra_paths), search_path])
    result: dict[str, dict[str, Any]] = {}
    for key, names in CLI_CANDIDATES:
        found = ""
        for name in names:
            found = shutil.which(name, path=search_path) or ""
            if found: break
        result[key] = {"ready": bool(found), "path": found, "candidates": list(names)}
    return result


def audit_project(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    try:
        from VaultSettings import load_settings
        config = load_settings().get("tooling") or {}
        include_archived = bool(config.get("includeArchivedTooling", False))
        extra = [Path(str(x)).expanduser() for x in config.get("extraSearchPaths", []) or []]
    except Exception:
        include_archived = False; extra = []
    tools = scan_scripts(root, include_archived=include_archived)
    commands = read_declared_commands(root)
    by_domain: dict[str, int] = {}
    for row in tools:
        by_domain[row.domain] = by_domain.get(row.domain, 0) + 1
    return {
        "schema": "vault.tooling.audit.v1",
        "version": TOOLING_VERSION,
        "root": str(root),
        "capturedUtc": datetime.now(timezone.utc).isoformat(),
        "scripts": [asdict(r) for r in tools],
        "scriptCount": len(tools),
        "domains": dict(sorted(by_domain.items())),
        "declaredCommands": commands,
        "commandCount": len(commands),
        "buildSystems": detect_build_systems(root),
        "cli": inventory_cli(extra),
        "blenderScripts": [asdict(r) for r in tools if r.domain == "blender"],
    }


def audit_registered_projects(*, max_projects: int = 500) -> dict[str, Any]:
    """Build a global, non-executing tool/script index for every registered project."""
    try:
        from PCCSurfaceCommon import ProjectRegistry
        from VaultPaths import vault_root
    except Exception as exc:
        raise RuntimeError(f"Vault project registry unavailable: {exc}") from exc
    projects: list[dict[str, Any]] = []
    domain_totals: dict[str, int] = {}
    script_total = 0; blender_total = 0; command_total = 0
    for entry in ProjectRegistry().entries()[:max_projects]:
        if not entry.root.is_dir():
            continue
        try:
            audit = audit_project(entry.root)
        except Exception as exc:
            projects.append({"projectId": entry.project_id, "name": entry.name, "root": str(entry.root), "error": str(exc)})
            continue
        scripts = audit.get("scripts") or []; blender = audit.get("blenderScripts") or []; commands = audit.get("declaredCommands") or []
        script_total += len(scripts); blender_total += len(blender); command_total += len(commands)
        for name, count in (audit.get("domains") or {}).items():
            domain_totals[str(name)] = domain_totals.get(str(name), 0) + int(count or 0)
        projects.append({
            "projectId": entry.project_id, "name": entry.name, "root": str(entry.root),
            "scriptCount": len(scripts), "commandCount": len(commands), "domains": audit.get("domains") or {},
            "buildSystems": audit.get("buildSystems") or [], "blenderScriptCount": len(blender), "scripts": scripts,
            "declaredCommands": commands,
        })
    result = {
        "schema": "vault.tooling.global-index.v1", "version": TOOLING_VERSION,
        "capturedUtc": datetime.now(timezone.utc).isoformat(), "projects": projects,
        "projectCount": len(projects), "scriptCount": script_total, "commandCount": command_total,
        "blenderScriptCount": blender_total, "domains": dict(sorted(domain_totals.items())), "cli": inventory_cli(),
    }
    out = vault_root() / "catalog" / "tooling" / "global-tool-index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp"); tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"); os.replace(tmp, out)
    result["report"] = str(out)
    return result


__all__ = ["ToolRecord", "audit_project", "audit_registered_projects", "detect_build_systems", "inventory_cli", "read_declared_commands", "read_declared_registry", "scan_scripts"]
