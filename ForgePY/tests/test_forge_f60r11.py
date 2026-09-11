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

from ForgeVersion import VERSION, BUILD
from PCCSurfaceCommon import ProjectRegistry
from VaultIntake import approve_manual_patch_for_project, counts_for_project, list_items, scan_roots


@contextmanager
def env(**values: str):
    old = {k: os.environ.get(k) for k in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def write_contract(root: Path, build: str = "B2") -> None:
    (root / "project.control.json").write_text(json.dumps({
        "schema": "forge.project.v1",
        "project": {"id": "demo", "name": "Demo", "kind": "python", "build": build, "version": "2.0"},
        "commands": [],
    }), encoding="utf-8")


def make_patch(path: Path, *, patch_id: str = "DEMO-MANUAL-001", build: str = "B2", project: str = "Demo") -> None:
    payload = b"manual-r11\n"
    manifest = {
        "schema": "forge.patch.v1",
        "engine": "forge-universal",
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "patchId": patch_id,
        "preconditions": {"projectBuild": build},
        "files": [{"path": "manual-r11.txt", "operation": "write", "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PATCH_MANIFEST.json", json.dumps(manifest))
        zf.writestr("payload/manual-r11.txt", payload)


class ForgeF60R11Tests(unittest.TestCase):
    def test_version_authority(self) -> None:
        self.assertEqual(VERSION, "0.4.22-F60R22")
        self.assertEqual(BUILD, "FORGEPY-F60R22")

    def test_descriptive_manual_patch_can_be_explicitly_queued_without_rename(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); project = base / "Demo"; project.mkdir(); downloads = base / "Downloads"; downloads.mkdir()
            write_contract(project)
            patch = base / "Demo_Descriptive_R11.patch"; make_patch(patch)
            with env(FORGE_PROJECT_REGISTRY=str(base / "registry.json"), FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(downloads)):
                ProjectRegistry().register(project, make_active=True)
                approved = approve_manual_patch_for_project(project, patch)
                self.assertEqual(approved["state"], "QUEUED", approved)
                self.assertEqual(approved["classification"], "PATCH-MANUAL-APPROVED", approved)
                self.assertTrue(patch.is_file(), "manual selection must retain the user's original transport")
                self.assertEqual(counts_for_project("demo", "Demo"), (1, 0))

    def test_manual_selection_can_recover_same_bytes_from_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); project = base / "Demo"; project.mkdir(); downloads = base / "Downloads"; downloads.mkdir()
            write_contract(project)
            root_patch = project / "Demo_Descriptive_R11.patch"; make_patch(root_patch, patch_id="DEMO-LINEAGE-001")
            retained_copy = base / "retained.patch"; retained_copy.write_bytes(root_patch.read_bytes())
            with env(FORGE_PROJECT_REGISTRY=str(base / "registry.json"), FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(downloads)):
                ProjectRegistry().register(project, make_active=True)
                result = scan_roots((project,), force_stable=True, remove_source=True, trusted_roots=(project,))
                self.assertEqual(result["ingested"][0]["state"], "LINEAGE", result)
                approved = approve_manual_patch_for_project(project, retained_copy)
                self.assertEqual(approved["state"], "QUEUED", approved)
                self.assertEqual(approved["classification"], "PATCH-MANUAL-APPROVED", approved)
                rows = list_items(project="Demo")
                self.assertEqual(len(rows), 1, rows)

    def test_wrong_project_manual_selection_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); project = base / "Demo"; project.mkdir(); downloads = base / "Downloads"; downloads.mkdir()
            write_contract(project)
            patch = base / "Other.patch"; make_patch(patch, project="Other")
            with env(FORGE_PROJECT_REGISTRY=str(base / "registry.json"), FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(downloads)):
                ProjectRegistry().register(project, make_active=True)
                with self.assertRaisesRegex(Exception, "project identity"):
                    approve_manual_patch_for_project(project, patch)
                self.assertEqual(counts_for_project("demo", "Demo"), (0, 0))
                self.assertTrue(patch.is_file())

    def test_gui_exposes_apply_patch_picker(self) -> None:
        text = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn('("Apply Patch…",', text)
        self.assertIn("vault_approve_manual_patch_for_project", text)
        self.assertIn('askopenfilename(', text)


if __name__ == "__main__":
    unittest.main()
