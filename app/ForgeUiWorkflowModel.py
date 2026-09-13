#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

UI_WORKFLOW_VERSION = "FORGEPY-UI-WORKFLOW-2.0-F700"

@dataclass(frozen=True)
class Surface:
    key: str
    label: str
    legacy_keys: tuple[str, ...] = ()
    description: str = ""

PRIMARY_SURFACES = (
    Surface("vault", "Vault", ("Projects", "Vault"), "Project library, intake, artifacts and project selection."),
    Surface("project", "Project", ("Project Workspace", "Dashboard"), "Selected-project dashboard, updates, source/recovery, diagnostics, tools and evidence."),
    Surface("workspace", "Workspace", ("IDE", "Cortex"), "Native project files, editing, quick-open and authoring beside the persistent Forge Console."),
    Surface("settings", "Settings", ("Settings",), "ForgePY configuration and integrations."),
)

LEGACY_TOP_LEVEL_HIDDEN = {
    "Operations", "Updates", "Projects", "Source Control", "Cortex", "Dashboard",
}

PROJECT_PAGES = {
    "Dashboard": "project.dashboard",
    "Updates": "project.updates",
    "Source Control": "project.source",
    "Diagnostics": "project.diagnostics",
    "Artifacts": "project.artifacts",
    "Recovery": "project.recovery",
}

# These labels are compatibility input only. New user-facing surfaces use the right side.
USER_FACING_RENAMES = {
    "PROJECT CONSOLE": "FORGE CONSOLE",
    "Project Console": "Forge Console",
    "Registered Projects": "Vault Projects",
    "Register Local...": "Add Local Project...",
    "Open Workspace": "Open Project",
    "Local Source": "ForgeGit",
    "LOCAL SOURCE": "FORGEGIT",
    "BACKUP SOURCE": "SNAPSHOT TO FORGEGIT",
    "RESTORE SOURCE": "RESTORE FROM FORGEGIT",
    "BACKUP TO GITHUB": "PUSH SNAPSHOT TO GITHUB",
    "IDE": "Workspace",
    "ForgePY IDE / Monaco Pop-out": "Workspace",
    "Enable IDE workspace": "Enable Workspace",
    "IDE Runtime": "Workspace Runtime",
    "Tooling": "Project Tools",
    "Advanced Commands": "Advanced",
}

LEGACY_WORKSPACE_BUTTONS = {
    "Install Monaco", "Install pywebview", "Open Monaco Window",
}

# Forge Console and Project CLI are intentionally distinct:
# - Forge Console is the permanently embedded ForgePY execution/output surface.
# - Project CLI opens the selected project's own CLI/PCC surface on explicit request.
PROJECT_CLI_MODE = "external-project-cli"
CONSOLE_LABEL = "FORGE CONSOLE"
PROJECT_NAV_HIDDEN = {"Build & Run"}

def primary_bindings() -> dict[str, str]:
    out: dict[str, str] = {}
    for surface in PRIMARY_SURFACES:
        for legacy in surface.legacy_keys:
            out[legacy] = surface.label
    return out


def surface_model() -> dict[str, Any]:
    return {
        "schema": "forgepy.ui-workflow.v1",
        "version": UI_WORKFLOW_VERSION,
        "primary": [asdict(x) for x in PRIMARY_SURFACES],
        "projectPages": dict(PROJECT_PAGES),
        "hiddenLegacyTopLevel": sorted(LEGACY_TOP_LEVEL_HIDDEN),
        "projectCliMode": PROJECT_CLI_MODE,
        "ownership": {
            "patchIntake": "right-rail",
            "projectOperations": "project",
            "sourceControl": "project+vault-summary",
            "fileCatalog": "vault.library",
            "authoring": "workspace",
            "console": "shared-project-console",
            "cortexExecution": "shared-project-console+operation-service",
        },
    }
