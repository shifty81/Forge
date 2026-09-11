#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

DISCOVERY_VERSION = "FORGE-DISCOVERY-0.4.9"


def _safe_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _risk(item: dict[str, Any]) -> str:
    raw = str(item.get("risk") or "").strip()
    if raw:
        return raw
    if bool(item.get("requiresConfirmation")):
        return "confirm"
    if bool(item.get("mutates")):
        return "write"
    return "read"


def _canonicalize_contract(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Normalize currently-known project.control.json shapes without rewriting the project.

    Older project PCCs used root-level id/name/type/executable/arguments fields while newer
    Cortex contracts use a nested project object and program/args.  The universal PCC accepts
    both and exposes one stable in-memory model.
    """
    project_obj = data.get("project") if isinstance(data.get("project"), dict) else {}
    project_id = str(
        project_obj.get("id")
        or data.get("id")
        or data.get("projectId")
        or root.name
    ).strip()
    name = str(project_obj.get("name") or data.get("name") or root.name).strip()
    kind = str(
        project_obj.get("kind")
        or data.get("kind")
        or data.get("type")
        or _detect_kind(root)
    ).strip()

    commands: list[dict[str, Any]] = []
    for item in data.get("commands", []) or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        program = str(item.get("program") or item.get("executable") or "").strip()
        args_raw = item.get("args") if item.get("args") is not None else item.get("arguments")
        args = [str(x) for x in (args_raw or [])]
        commands.append({
            "key": key,
            "label": str(item.get("label") or key),
            "risk": _risk(item),
            "program": program,
            "args": args,
            "category": str(item.get("category") or "").strip(),
            "mutates": bool(item.get("mutates")),
            "requiresConfirmation": bool(item.get("requiresConfirmation")),
        })

    gate_keys: list[str] = []
    for item in data.get("quality_gates", []) or []:
        if isinstance(item, dict) and item.get("key"):
            gate_keys.append(str(item["key"]))
    if not gate_keys:
        gate_keys = [
            cmd["key"] for cmd in commands
            if cmd["category"].casefold() == "gate" or cmd["key"].casefold().startswith("gate.")
        ]

    root_control = data.get("root_control_center") if isinstance(data.get("root_control_center"), dict) else {}
    root_launcher = str(
        root_control.get("launcher")
        or data.get("rootLauncher")
        or data.get("root_launcher")
        or ""
    ).strip()
    state_dir = str(data.get("stateDirectory") or data.get("state_directory") or "").strip()

    normalized = dict(data)
    normalized["project"] = {**project_obj, "id": project_id, "name": name, "kind": kind}
    normalized["commands"] = commands
    normalized["quality_gates"] = [{"key": key} for key in gate_keys]
    normalized["root_control_center"] = {
        **root_control,
        "launcher": root_launcher,
    }
    normalized["stateDirectory"] = state_dir
    normalized["_pccDiscovery"] = {
        "version": DISCOVERY_VERSION,
        "source": "project.control.json",
        "contractShape": "nested" if project_obj else "root-level",
    }
    return normalized


def _stardew_manifest(root: Path) -> dict[str, Any] | None:
    # SMAPI mods/content packs normally expose manifest.json at the mod root. Some authoring
    # repositories keep the distributable mod one level below the repo, so inspect shallowly.
    candidates = [root / "manifest.json"]
    try:
        candidates.extend(sorted(root.glob("*/manifest.json"))[:32])
    except OSError:
        pass
    for path in candidates:
        data = _safe_json(path)
        if not data:
            continue
        if data.get("UniqueID") and (data.get("EntryDll") or data.get("ContentPackFor")):
            data = dict(data)
            data["_path"] = str(path)
            return data
    return None


def _dotnet_target(root: Path) -> Path | None:
    slns = sorted(root.glob("*.sln"))
    if slns:
        return slns[0]
    projects = sorted(root.glob("*.csproj"))
    if projects:
        return projects[0]
    # Common source layouts, but stay shallow to avoid binding an arbitrary test/sample project.
    for folder_name in ("src", "Source", "source"):
        folder = root / folder_name
        if not folder.is_dir():
            continue
        projects = sorted(folder.glob("*.csproj"))
        if len(projects) == 1:
            return projects[0]
    return None


def _stardew_tooling_script(root: Path) -> Path | None:
    candidates = [
        root / "tools" / "control" / "StardewModdingKitTools.ps1",
        root / "StardewModdingKitTools.ps1",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _detect_kind(root: Path) -> str:
    stardew = _stardew_manifest(root)
    if stardew:
        return "stardew-smapi-mod" if stardew.get("EntryDll") else "stardew-content-pack"
    if _stardew_tooling_script(root) is not None:
        return "stardew-toolkit"
    if (root / "Cargo.toml").is_file():
        return "rust-workspace"
    if (root / "CMakeLists.txt").is_file() or (root / "engine" / "CMakeLists.txt").is_file():
        return "native-cpp"
    if (root / "gradlew").is_file() or (root / "gradlew.bat").is_file() or (root / "build.gradle").is_file():
        return "java-gradle"
    if _dotnet_target(root) is not None:
        return "dotnet"
    if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        return "python"
    if (root / "package.json").is_file():
        return "node"
    return "project"


_ACTION_TO_KEY = {
    "status": "project.status",
    "project-status": "project.status",
    "health": "project.health",
    "environment-status": "project.environment",
    "environment": "project.environment",
    "control-center-self-test": "project.self-test",
    "self-test": "project.self-test",
    "full-gate": "gate.full",
    "clean-full-gate": "gate.clean-full",
    "fast-gate": "gate.fast",
    "quick-gate": "gate.fast",
    "build": "build.native",
    "build-render": "build.native",
    "build-headless": "build.headless",
    "test": "test.native",
    "run-game": "run.game",
    "run-client": "run.game",
    "run-editor": "run.editor",
    "run-shipyard": "run.shipyard",
    "run-smoke": "run.smoke",
    "patch-status": "patch.status",
    "preview-inbox": "patch.preview",
    "apply-inbox": "patch.apply",
    "undo-last-patch": "recovery.undo-last",
    "root-audit": "audit.root",
    "pass-continuity": "audit.continuity",
    "source-authority": "source.authority",
    "debug-bundle": "diagnostics.bundle",
    "source-rollup": "package.source-rollup",
    "asset-rollup": "package.asset-rollup",
    "capture-baseline": "package.baseline",
    "incremental-handoff": "package.incremental",
    "artifact-index": "artifacts.index",
    "dependency-status": "dependencies.status",
    "git-status": "git.status",
    "git-history": "git.history",
    "git-commit-green": "git.commit-green",
    "git-push": "git.push",
    "git-pull": "git.pull",
    "git-repair": "git.repair-working-copy",
    "repo-authority-audit": "repo.audit",
    "repo-authority-prepare": "repo.prepare",
    "repo-authority-publish": "repo.publish",
    "open-latest-debug": "diagnostics.open-latest",
}


def _action_key(action: str) -> str:
    return _ACTION_TO_KEY.get(action.casefold(), f"legacy.{action.strip().lower().replace('_', '-')}")


def _action_category(key: str) -> str:
    return key.split(".", 1)[0] if "." in key else "project"


def _powershell_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []
    explicit = [
        root / "tools" / "control" / "ProjectControlCenter.ps1",
        root / "tools" / "control" / "ControlCenter.ps1",
    ]
    candidates.extend(path for path in explicit if path.is_file())
    control_dir = root / "tools" / "control"
    if control_dir.is_dir():
        # Existing project utilities are donors, not something Vault should replace. This is
        # what lets e.g. tools/control/StardewModdingKitTools.ps1 become executable instead of
        # merely showing up in the file catalog.
        candidates.extend(sorted(control_dir.glob("*ControlCenter.ps1")))
        candidates.extend(sorted(control_dir.glob("*Tools.ps1")))
        candidates.extend(sorted(control_dir.glob("*.ps1")))
    tools_dir = root / "tools"
    if tools_dir.is_dir():
        candidates.extend(sorted(tools_dir.glob("*Tools.ps1")))
        candidates.extend(sorted(tools_dir.glob("*ControlCenter.ps1")))
    candidates.extend(sorted(root.glob("*Tools.ps1")))
    candidates.extend(sorted(root.glob("*ControlCenter.ps1")))
    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = os.path.normcase(str(path.resolve()))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _extract_actions(ps1: Path) -> list[str]:
    try:
        text = ps1.read_text(encoding="utf-8-sig", errors="replace")[:60000]
    except OSError:
        return []
    # Prefer the ValidateSet directly attached to the $Action parameter.
    pattern = re.compile(
        r"\[ValidateSet\((?P<body>.*?)\)\]\s*\[string\]\s*\$Action\b",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        # Some scripts put attributes/whitespace between ValidateSet and the type.
        match = re.search(
            r"\[ValidateSet\((?P<body>.*?)\)\].{0,240}?\$Action\b",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if match:
        values = re.findall(r"['\"]([^'\"]+)['\"]", match.group("body"))
    else:
        values = []
        # Older project utilities often use an unconstrained $Action parameter with a
        # switch statement instead of ValidateSet. Recover those explicit action literals
        # without inventing operations that the script never declared.
        if re.search(r"\$Action\b", text, re.IGNORECASE):
            for switch_match in re.finditer(r"switch\s*\(\s*\$Action\s*\)\s*\{(?P<body>.*?)\n\}", text, re.IGNORECASE | re.DOTALL):
                values.extend(re.findall(r"(?m)^\s*['\"]([^'\"]+)['\"]\s*\{", switch_match.group("body")))
            values.extend(re.findall(r"\$Action\s*(?:-eq|==)\s*['\"]([^'\"]+)['\"]", text, re.IGNORECASE))
        if not values:
            return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip()
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            out.append(value)
    return out




def _ps_single_quoted(value: str) -> str:
    return value.replace("'", "''")


def _discover_command_registry(root: Path, script: Path) -> list[dict[str, Any]]:
    """Discover command-registry based project PCCs without executing them.

    Mature projects such as Havenwild accept ``-Command <registry-key>`` and load a
    ProjectCommandRegistry.ps1.  That is a stronger project authority than generic Cargo/CMake
    inference, so Forge exposes the registry keys through the existing project launcher.
    """
    try:
        text = script.read_text(encoding="utf-8-sig", errors="replace")[:120000]
    except OSError:
        return []
    if not re.search(r"\$Command\b", text, re.IGNORECASE):
        return []
    registry_match = re.search(r"""['"]([^'"]*ProjectCommandRegistry\.ps1)['"]""", text, re.IGNORECASE)
    if registry_match:
        candidate = (script.parent / registry_match.group(1)).resolve()
    else:
        candidate = script.parent / "ProjectCommandRegistry.ps1"
    if not candidate.is_file():
        return []
    try:
        registry_text = candidate.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []

    rel = script.relative_to(root).as_posix()
    commands: list[dict[str, Any]] = []
    canonical_added: set[str] = set()
    # Registry entries are intentionally shallow PowerShell hashtables.  Match each entry
    # independently; fields may be separated by arbitrary whitespace/newlines.
    for match in re.finditer(r"@\{(?P<body>.*?)\}", registry_text, re.DOTALL):
        body = match.group("body")
        key_m = re.search(r"""\bKey\s*=\s*['"]([^'"]+)['"]""", body, re.IGNORECASE)
        if not key_m:
            continue
        key = key_m.group(1).strip()
        if not key:
            continue
        label_m = re.search(r"""\bLabel\s*=\s*['"]([^'"]+)['"]""", body, re.IGNORECASE)
        kind_m = re.search(r"""\bKind\s*=\s*['"]([^'"]+)['"]""", body, re.IGNORECASE)
        category_m = re.search(r"""\bCategory\s*=\s*['"]([^'"]+)['"]""", body, re.IGNORECASE)
        label = label_m.group(1).strip() if label_m else key
        kind = kind_m.group(1).strip() if kind_m else ""
        category = category_m.group(1).strip() if category_m else _action_category(key)
        lowered = key.casefold()
        mutates = any(token in lowered for token in (
            "build", "apply", "commit", "push", "repair", "package", "capture",
            "publish", "clean", "restore", "undo", "regenerate",
        )) or kind.casefold() in {"build", "package", "builtinqualitygate", "builtinfastqualitygate"}
        confirm = any(token in lowered for token in ("apply", "commit", "push", "repair", "publish", "undo", "restore"))
        row = {
            "key": key,
            "label": label,
            "risk": "write" if mutates else "read",
            "program": "powershell",
            "args": ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", rel, "-Command", key],
            "category": category,
            "mutates": mutates,
            "requiresConfirmation": confirm,
        }
        commands.append(row)

        canonical = ""
        if kind.casefold() == "builtinqualitygate" or lowered in {
            "validation.full-quality-gate", "quality.full", "full-quality-gate"
        }:
            canonical = "gate.full"
        elif kind.casefold() == "builtinfastqualitygate" or lowered in {
            "validation.fast-quality-gate", "quality.fast", "fast-quality-gate"
        }:
            canonical = "gate.fast"
        elif lowered in {"build.all", "build.workspace", "build.project"}:
            canonical = "build.native"
        if canonical and canonical not in canonical_added:
            alias = dict(row)
            alias["key"] = canonical
            alias["label"] = label
            alias["category"] = _action_category(canonical)
            commands.insert(0, alias)
            canonical_added.add(canonical)
    return commands

def _discover_from_powershell(root: Path) -> tuple[list[dict[str, Any]], str, str]:
    for script in _powershell_candidates(root):
        rel = script.relative_to(root).as_posix()
        registry_commands = _discover_command_registry(root, script)
        if registry_commands:
            launcher = ""
            for candidate in (root / "PROJECT_CONTROL_CENTER.cmd", root / (script.stem + ".cmd")):
                if candidate.is_file():
                    launcher = candidate.relative_to(root).as_posix()
                    break
            return registry_commands, rel, launcher
        actions = _extract_actions(script)
        if not actions:
            # A menu-driven utility is still executable tooling. Expose it explicitly rather
            # than reducing a project to scan-only mode, while avoiding guessed build actions.
            if script.stem.casefold().endswith("tools") or "control" in script.stem.casefold():
                return [{
                    "key": "run.project-tools",
                    "label": f"Open {script.stem}",
                    "risk": "read",
                    "program": "powershell",
                    "args": ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", rel],
                    "category": "run",
                    "mutates": False,
                    "requiresConfirmation": False,
                }], rel, ""
            continue
        commands: list[dict[str, Any]] = []
        for action in actions:
            if action.casefold() == "menu":
                continue
            key = _action_key(action)
            mutates = any(token in key for token in ("build", "apply", "commit", "push", "repair", "package", "capture", "publish"))
            args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", rel, "-Action", action]
            commands.append({
                "key": key,
                "label": action.replace("-", " ").title(),
                "risk": "write" if mutates else "read",
                "program": "powershell",
                "args": args,
                "category": _action_category(key),
                "mutates": mutates,
                "requiresConfirmation": any(token in key for token in ("apply", "commit", "push", "repair", "publish")),
            })
        launcher = ""
        for candidate in (root / "PROJECT_CONTROL_CENTER.cmd", root / (script.stem + ".cmd")):
            if candidate.is_file():
                launcher = candidate.relative_to(root).as_posix()
                break
        return commands, rel, launcher
    return [], "", ""


def _discover_name(root: Path, ps_script: str = "") -> str:
    stem = Path(ps_script).stem if ps_script else ""
    for suffix in ("ControlCenter", "ProjectControlCenter", "Tools"):
        if stem.casefold().endswith(suffix.casefold()) and len(stem) > len(suffix):
            return stem[: -len(suffix)].replace("_", " ").replace("-", " ").strip()
    return root.name



def _command(key: str, label: str, program: str, args: list[str], *, category: str | None = None, mutates: bool = False, confirm: bool = False, risk: str | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "risk": risk or ("write" if mutates else "read"),
        "program": program,
        "args": [str(x) for x in args],
        "category": category or _action_category(key),
        "mutates": bool(mutates),
        "requiresConfirmation": bool(confirm),
    }


def _merge_commands(primary: list[dict[str, Any]], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*primary, *fallback]:
        key = str(item.get("key") or "").strip()
        if not key or key.casefold() in seen:
            continue
        seen.add(key.casefold())
        out.append(item)
    return out


def _infer_generic_commands(root: Path) -> list[dict[str, Any]]:
    """Create a safe local adapter when a project has no explicit PCC contract.

    This never writes into the project.  It derives only commands that can be justified by
    standard build markers already present in the repository.  Explicit project contracts
    and root utilities always outrank these inferred fallbacks.
    """
    commands: list[dict[str, Any]] = []
    commands.append(_command("project.status", "Project / Git status", "__pcc_internal__", ["status"], category="project"))
    commands.append(_command("project.health", "Detected project health", "__pcc_internal__", ["health"], category="project"))
    if (root / ".git").exists():
        commands.extend([
            _command("git.status", "Git status", "git", ["-C", "{root}", "status", "--short", "--branch"], category="git"),
            _command("git.history", "Git history", "git", ["-C", "{root}", "log", "--oneline", "--decorate", "--graph", "-20"], category="git"),
            _command("git.commit-green", "Commit certified GREEN source", "__pcc_internal__", ["git-commit-green"], category="git", mutates=True, confirm=True),
            _command("git.push", "Push current branch", "__pcc_internal__", ["git-push-current"], category="git", mutates=True, confirm=True),
            _command("git.pull", "Pull fast-forward only", "git", ["-C", "{root}", "pull", "--ff-only"], category="git", mutates=True, confirm=True),
        ])

    if (root / "Cargo.toml").is_file():
        commands.extend([
            _command("gate.full", "Full Rust quality gate", "__pcc_internal__", ["rust-full-gate"], category="gate", mutates=True),
            _command("gate.fast", "Fast Rust development gate", "cargo", ["check", "--workspace", "--all-targets"], category="gate"),
            _command("build.native", "Build Rust workspace", "cargo", ["build", "--workspace"], category="build", mutates=True),
            _command("test.native", "Test Rust workspace", "cargo", ["test", "--workspace", "--all-targets"], category="test"),
        ])

    gradle = root / "gradlew.bat" if (root / "gradlew.bat").is_file() else (root / "gradlew" if (root / "gradlew").is_file() else None)
    if gradle is not None:
        program = str(gradle.name)
        commands.extend([
            _command("gate.full", "Full Gradle quality gate", program, ["check"], category="gate", mutates=True),
            _command("gate.fast", "Fast Gradle check", program, ["test"], category="gate"),
            _command("build.native", "Gradle build", program, ["build"], category="build", mutates=True),
            _command("test.native", "Gradle tests", program, ["test"], category="test"),
        ])

    dotnet_target = _dotnet_target(root)
    stardew = _stardew_manifest(root)
    if dotnet_target is not None:
        rel_target = dotnet_target.relative_to(root).as_posix()
        commands.extend([
            _command("gate.full", "Full .NET quality gate", "__pcc_internal__", ["dotnet-full-gate", rel_target], category="gate", mutates=True),
            _command("gate.fast", ".NET build check", "dotnet", ["build", rel_target], category="gate", mutates=True),
            _command("build.native", "Build .NET project", "dotnet", ["build", rel_target], category="build", mutates=True),
            _command("build.release", "Build .NET Release", "dotnet", ["build", rel_target, "-c", "Release"], category="build", mutates=True),
        ])
        test_markers = list(root.glob("*Tests*.csproj")) + list(root.glob("tests/**/*.csproj"))
        if test_markers:
            commands.append(_command("test.native", ".NET tests", "dotnet", ["test", rel_target], category="test"))
    elif stardew and stardew.get("ContentPackFor"):
        commands.append(_command("gate.fast", "Validate Stardew content pack JSON", "__pcc_internal__", ["stardew-content-validate"], category="gate"))
        commands.append(_command("gate.full", "Full Stardew content-pack validation", "__pcc_internal__", ["stardew-content-validate"], category="gate"))

    if (root / "package.json").is_file():
        try:
            package = _safe_json(root / "package.json") or {}
            scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
        except Exception:
            scripts = {}
        runner = "npm"
        if "test" in scripts:
            commands.append(_command("test.native", "NPM tests", runner, ["test", "--"], category="test"))
        if "build" in scripts:
            commands.append(_command("build.native", "NPM build", runner, ["run", "build"], category="build", mutates=True))
        if "lint" in scripts:
            commands.append(_command("gate.fast", "NPM lint", runner, ["run", "lint"], category="gate"))
        if "build" in scripts and "test" in scripts:
            commands.append(_command("gate.full", "Full Node quality gate", "__pcc_internal__", ["node-full-gate"], category="gate", mutates=True))
        for run_name in ("dev", "start"):
            if run_name in scripts:
                commands.append(_command("run.runtime", f"NPM {run_name}", runner, ["run", run_name], category="run"))
                break

    if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        commands.extend([
            _command("gate.fast", "Python compile check", "python", ["-m", "compileall", "-q", "."], category="gate"),
            _command("test.native", "Python unittest discovery", "python", ["-m", "unittest", "discover"], category="test"),
        ])

    cmake_root = root if (root / "CMakeLists.txt").is_file() else (root / "engine" if (root / "engine" / "CMakeLists.txt").is_file() else None)
    if cmake_root is not None:
        # Build-only fallbacks are intentionally conservative: configure details vary heavily.
        for build_dir_name in ("build", "Build", "build-debug", "Builds/windows-x64-debug", "engine/build"):
            build_dir = root / build_dir_name
            if build_dir.is_dir():
                commands.append(_command("build.native", "Build existing CMake tree", "cmake", ["--build", str(build_dir)], category="build", mutates=True))
                break

    return _merge_commands([], commands)


def _infer_project_name(root: Path, fallback: str) -> str:
    # Gradle settings are a particularly useful source for JSON-less Java projects.
    for settings in (root / "settings.gradle", root / "settings.gradle.kts"):
        if settings.is_file():
            try:
                text = settings.read_text(encoding="utf-8-sig", errors="replace")[:20000]
                match = re.search(r"rootProject\.name\s*=\s*['\"]([^'\"]+)['\"]", text)
                if match:
                    return match.group(1).strip()
            except OSError:
                pass
    return fallback

def discover_project_contract_data(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    contract_path = root / "project.control.json"
    if contract_path.is_file():
        data = _safe_json(contract_path)
        if data is not None:
            normalized = _canonicalize_contract(root, data)
            inferred = _infer_generic_commands(root)
            normalized["commands"] = _merge_commands(list(normalized.get("commands") or []), inferred)
            if not normalized.get("quality_gates"):
                normalized["quality_gates"] = [
                    {"key": c["key"]} for c in normalized["commands"] if str(c.get("key") or "").startswith("gate.")
                ]
            discovery = normalized.setdefault("_pccDiscovery", {})
            discovery["inferredCommands"] = len(inferred)
            discovery["provider"] = str((normalized.get("root_control_center") or {}).get("machine_provider") or "project.control.json")
            return normalized

    commands, ps_script, launcher = _discover_from_powershell(root)
    inferred = _infer_generic_commands(root)
    commands = _merge_commands(commands, inferred)
    kind = _detect_kind(root)
    name = _infer_project_name(root, _discover_name(root, ps_script))
    markers = {
        "cargo": (root / "Cargo.toml").is_file(),
        "cmake": (root / "CMakeLists.txt").is_file() or (root / "engine" / "CMakeLists.txt").is_file(),
        "gradle": (root / "gradlew").is_file() or (root / "gradlew.bat").is_file(),
        "dotnet": _dotnet_target(root) is not None,
        "stardew": _stardew_manifest(root) is not None,
        "stardewTooling": _stardew_tooling_script(root) is not None,
        "python": (root / "pyproject.toml").is_file(),
        "node": (root / "package.json").is_file(),
        "git": (root / ".git").exists(),
    }
    return {
        "project": {"id": root.name.lower().replace(" ", "-"), "name": name, "kind": kind},
        "commands": commands,
        "quality_gates": [{"key": c["key"]} for c in commands if c["key"].startswith("gate.")],
        "root_control_center": {"launcher": launcher, "discoveredPowerShell": ps_script},
        "stateDirectory": "",
        "_pccDiscovery": {
            "version": DISCOVERY_VERSION,
            "source": "filesystem-scan",
            "markers": markers,
            "provider": ps_script or "generated-local-adapter",
            "explicitProvider": bool(ps_script),
            "inferredCommands": len(inferred),
        },
    }


def discovery_summary(root: Path) -> dict[str, Any]:
    data = discover_project_contract_data(root)
    discovery = data.get("_pccDiscovery") or {}
    commands = data.get("commands") or []
    project = data.get("project") or {}
    return {
        "name": project.get("name") or root.name,
        "kind": project.get("kind") or "project",
        "source": discovery.get("source") or "unknown",
        "provider": discovery.get("provider") or (data.get("root_control_center") or {}).get("launcher") or "",
        "commands": len(commands),
        "commandKeys": [str(x.get("key")) for x in commands if isinstance(x, dict) and x.get("key")],
        "markers": discovery.get("markers") or {},
    }
