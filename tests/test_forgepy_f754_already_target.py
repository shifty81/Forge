from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from PCCSurfaceCommon import ProjectRegistry
from ForgePYIntake import resolve_patch_target, retain_already_applied_patch
from ForgePYPatchEngine import target_satisfaction


@contextmanager
def env(**values: str):
    old = {k: os.environ.get(k) for k in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def write_project(root: Path, *, build: str = "DEMO-B2", version: str = "2.0") -> None:
    (root / "project.control.json").write_text(json.dumps({
        "schema": "forge.project.v1",
        "project": {"id": "demo", "name": "Demo", "kind": "python", "build": build, "version": version},
        "commands": [],
    }), encoding="utf-8")


def write_patch(path: Path, *, payload: bytes = b"target\n") -> None:
    manifest = {
        "schema": "forge.patch.v1",
        "engine": "forge-universal",
        "project": "Demo",
        "patchId": "DEMO-B2-CUMULATIVE",
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "preconditions": {"projectBuild": "DEMO-B1"},
        "target": {"projectBuild": "DEMO-B2", "projectVersion": "2.0"},
        "files": [{
            "path": "target.txt", "operation": "write", "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "preSha256": hashlib.sha256(b"base\n").hexdigest(),
        }],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PATCH_MANIFEST.json", json.dumps(manifest))
        zf.writestr("payload/target.txt", payload)


class ForgePYF754AlreadyTargetTests(unittest.TestCase):
    def test_patch_engine_reports_fully_materialized_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); project = base / "Demo"; project.mkdir()
            write_project(project)
            (project / "target.txt").write_bytes(b"target\n")
            patch = base / "Demo.patch"; write_patch(patch)
            result = target_satisfaction(patch, project)
            self.assertEqual(result["status"], "ALREADY_TARGET", result)
            self.assertEqual(result["satisfied"], result["total"])
            self.assertTrue(result["identityMatch"])

    def test_resolver_returns_already_target_instead_of_incompatible(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); project = base / "Demo"; project.mkdir(); downloads = base / "Downloads"; downloads.mkdir()
            write_project(project)
            (project / "target.txt").write_bytes(b"target\n")
            patch = base / "Demo.patch"; write_patch(patch)
            with env(FORGE_PROJECT_REGISTRY=str(base / "registry.json"), FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(downloads)):
                ProjectRegistry().register(project, make_active=True)
                result = resolve_patch_target(patch)
                self.assertEqual(result["status"], "ALREADY_TARGET", result)
                self.assertEqual(Path(result["targetRoot"]), project.resolve())
                self.assertEqual(result["routing"], "FORGEPY-F754-ALREADY-TARGET")

    def test_already_applied_transport_is_retained_as_inert_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); project = base / "Demo"; project.mkdir(); downloads = base / "Downloads"; downloads.mkdir()
            write_project(project)
            (project / "target.txt").write_bytes(b"target\n")
            patch = base / "Demo.patch"; write_patch(patch)
            with env(FORGE_PROJECT_REGISTRY=str(base / "registry.json"), FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(downloads)):
                ProjectRegistry().register(project, make_active=True)
                resolution = resolve_patch_target(patch)
                item = retain_already_applied_patch(patch, resolution)
                self.assertEqual(item["state"], "LINEAGE", item)
                self.assertEqual(item["classification"], "PATCH-LINEAGE-ALREADY-APPLIED", item)
                self.assertEqual(item["relationship"], "already-applied")
                self.assertFalse(patch.exists())
                self.assertTrue(Path(item["vault_path"]).is_file())

    def test_gui_has_non_warning_already_applied_path(self) -> None:
        text = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn('resolution_status == "ALREADY_TARGET"', text)
        self.assertIn('"Patch Already Applied"', text)
        self.assertIn('vault_retain_already_applied_patch', text)
        self.assertIn('No files were modified.', text)

    def test_candidate_identity_is_f754(self) -> None:
        from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
        self.assertEqual(DISPLAY_BUILD, "FORGEPY-F777")
        self.assertEqual(DISPLAY_VERSION, "0.5.0-candidate.777")


if __name__ == "__main__":
    unittest.main()
