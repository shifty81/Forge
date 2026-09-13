#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

AUDIT_VERSION = "FORGEPY-NORMALIZATION-AUDIT-2.8-F787"


def audit(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    from ForgeUiWorkflowModel import PRIMARY_SURFACES, PROJECT_CLI_MODE
    labels = [surface.label for surface in PRIMARY_SURFACES]
    add("primary-navigation", labels == ["Vault", "Project", "Workspace", "Settings"], " / ".join(labels))
    add("project-cli-mode", PROJECT_CLI_MODE == "external-project-cli", PROJECT_CLI_MODE)
    try:
        from ForgeApplicationIdentity import DISPLAY_VERSION, DISPLAY_BUILD
        add("candidate-identity", DISPLAY_VERSION == "0.5.0-candidate.797" and DISPLAY_BUILD == "FORGEPY-F797", f"{DISPLAY_VERSION} / {DISPLAY_BUILD}")
    except Exception as exc:
        add("candidate-identity", False, str(exc))
    try:
        from ForgeInstallerRuntime import choices
        modes={row.get("mode") for row in choices()}
        add("install-modes", modes == {"installed","portable"}, repr(sorted(modes)))
    except Exception as exc:
        add("install-modes", False, str(exc))
    add("self-maintenance-lane", (root/"app"/"ForgeSelfMaintenance.py").is_file(), "separate application update lane")
    add("executable-system", (root/"app"/"ForgeExecutableSystem.py").is_file(), "Nuitka/portable/installer/update-bundle distribution lane")
    add("navigation-runtime", (root/"app"/"ForgeNavigationRuntime.py").is_file(), "latest-request-wins app navigation")
    update_text=(root/"app"/"ForgeSelfUpdateRuntime.py").read_text(encoding="utf-8-sig") if (root/"app"/"ForgeSelfUpdateRuntime.py").is_file() else ""
    add("no-single-exe-updater", "mixed-version install" in update_text and "ForgeSelfMaintenance" in update_text, "legacy single-EXE updater disabled")
    add("functional-dashboard", (root/"app"/"ForgeProjectDashboard.py").is_file(), "project command-center dashboard")
    add("lazy-project-pages", (root/"app"/"ForgeProjectSurface.py").is_file(), "specialist Project pages are lazy")
    add("project-aware-branding", (root/"app"/"ForgeProjectBranding.py").is_file(), "quickbar project identity/icon resolver")
    add("rust-shadow-foundation", all((root/path).is_file() for path in (
        "native/forge-rs/Cargo.toml", "native/forge-rs/src/lib.rs", "native/forge-rs/src/identity.rs",
        "native/forge-rs/src/contracts.rs", "native/forge-rs/src/operations.rs", "native/forge-rs/src/transactions.rs",
        "native/forge-rs/src/parity.rs", "native/forge-rs/src/protocol.rs", "native/forge-rs/src/process_host.rs",
        "native/forge-rs/src/jobs.rs", "native/forge-rs/src/settings.rs", "native/forge-rs/src/project.rs",
        "native/forge-rs/src/journal.rs", "native/forge-rs/src/shell.rs", "native/forge-rs/src/evidence.rs",
        "tools/rust/ForgeRustLane.py",
    )), "governed native Rust SHADOW foundation")
    try:
        from ForgeLayoutNormalization import LAYOUT_VERSION
        add("layout-policy", bool(LAYOUT_VERSION), LAYOUT_VERSION)
    except Exception as exc:
        add("layout-policy", False, str(exc))

    from ForgePackagePolicy import classification, is_governed
    add("root-app-governed", is_governed("app/ForgeGui.py"), classification("app/ForgeGui.py"))
    add("nested-mirror-excluded", not is_governed("ForgePY/app/ForgeGui.py"), classification("ForgePY/app/ForgeGui.py"))
    add("runtime-output-excluded", not is_governed("logs/x.log"), classification("logs/x.log"))

    from ForgeProjectProtocol import protocol_conflicts
    conflicts = protocol_conflicts()
    add("protocol-alias-conflicts", not conflicts, repr(conflicts))

    try:
        from PCCOperationHost import AUTO_PATCH_OPERATIONS
        add("no-implicit-patch-apply", not AUTO_PATCH_OPERATIONS, repr(AUTO_PATCH_OPERATIONS))
    except ModuleNotFoundError:
        host = root / "app" / "PCCOperationHost.py"
        source = host.read_text(encoding="utf-8-sig") if host.is_file() else ""
        explicit_empty = bool(re.search(r"AUTO_PATCH_OPERATIONS\s*:\s*set\[str\]\s*=\s*set\(\)", source))
        add("no-implicit-patch-apply", explicit_empty, "static overlay proof")
    except Exception as exc:
        add("no-implicit-patch-apply", False, str(exc))

    cmd = (root / "Forge.cmd").read_text(encoding="utf-8-sig") if (root / "Forge.cmd").is_file() else ""
    add("root-cli-routing", "ForgeUnifiedCli.py" in cmd, "canonical CLI route" if "ForgeUnifiedCli.py" in cmd else "missing")

    workspace = root / "app" / "ForgeWorkspaceSurface.py"
    ws = workspace.read_text(encoding="utf-8-sig") if workspace.is_file() else ""
    add("native-workspace", bool(ws) and "Monaco" not in ws and "pywebview" not in ws, "native lazy Workspace")

    try:
        from ForgeStandaloneBuild import command
        argv = command(root)
        add("portable-executable", "--onefile" not in argv and "--standalone" in argv, " ".join(argv))
    except Exception as exc:
        add("portable-executable", False, str(exc))

    failed = [row for row in checks if not row["ok"]]
    return {
        "schema": "forgepy.normalization-audit.v1",
        "version": AUDIT_VERSION,
        "ok": not failed,
        "checks": checks,
        "failed": failed,
    }
