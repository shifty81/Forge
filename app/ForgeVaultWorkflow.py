#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


VAULT_WORKFLOW_VERSION = "FORGEPY-VAULT-WORKFLOW-1.1-F566"


@dataclass(frozen=True)
class VaultProjectRow:
    registry_id: str
    project_id: str
    name: str
    kind: str
    root: str
    github: str = ""
    integration_grade: str = "DISCOVERED"
    queued_updates: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def project_rows(*, with_audit: bool = False) -> list[dict[str, Any]]:
    from PCCSurfaceCommon import ProjectRegistry
    rows: list[dict[str, Any]] = []
    for entry in ProjectRegistry().entries():
        grade = "DISCOVERED"
        queued = 0
        if with_audit:
            try:
                from ForgeProjectAudit import audit as audit_project
                report = audit_project(Path(entry.root), deep=False)
                grade = str((report.get("protocol") or {}).get("grade") or grade)
                queued = int((report.get("updates") or {}).get("queued") or 0)
            except Exception:
                pass
        rows.append(
            VaultProjectRow(
                registry_id=entry.registry_id,
                project_id=entry.project_id,
                name=entry.name,
                kind=entry.kind,
                root=str(entry.root),
                github=entry.github_url,
                integration_grade=grade,
                queued_updates=queued,
            ).to_dict()
        )
    rows.sort(key=lambda row: str(row["name"]).casefold())
    return rows


def workflow() -> dict[str, Any]:
    return {
        "schema": "forgepy.vault-workflow.v1",
        "version": VAULT_WORKFLOW_VERSION,
        "startupSurface": "vault.projects",
        "steps": [
            {"key": "project.add", "label": "Add or Clone Project"},
            {"key": "project.select", "label": "Select Project"},
            {"key": "project.audit", "label": "Audit / Standardize"},
            {"key": "project.open", "label": "Open Project Dashboard"},
            {"key": "project.operate", "label": "Build / Test / Run / Updates"},
        ],
        "advanced": [
            {"key": "vault.library", "label": "Library / Catalog"},
            {"key": "vault.artifacts", "label": "Artifact Central"},
            {"key": "vault.recovery", "label": "Recovery / Backups"},
            {"key": "vault.source-summary", "label": "Selected Project Source Summary"},
            {"key": "vault.patch-intake", "label": "Patch Intake (right rail)"},
        ],
        "handoff": {
            "openProject": "Project Dashboard",
            "sourceControl": "Project / Source Control",
            "updates": "Project / Updates",
            "authoring": "Workspace",
            "console": "Forge Console",
        },
    }
