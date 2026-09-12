from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from VaultIntake import (
    approve_available_for_project,
    available_for_project,
    counts_for_project,
    list_items,
    scan_downloads,
    scan_roots,
    stage_for_project,
)
from VaultPatchEngine import apply_inbox


@contextmanager
def env(**values: str):
    old = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def write_contract(root: Path) -> None:
    data = {
        "schema": "project.control.v1",
        "project": {"id": "demo", "name": "Demo", "kind": "python", "build": "demo-build"},
        "commands": [],
    }
    (root / "project.control.json").write_text(json.dumps(data), encoding="utf-8")


def make_patch(path: Path, *, patch_id: str = "DEMO-R8-001", project: str = "Demo") -> None:
    payload = b"hello-r8\n"
    digest = hashlib.sha256(payload).hexdigest()
    manifest = {
        "schema": "forge.patch.v1",
        "engine": "forge-universal",
        "createdUtc": "2026-09-10T04:45:00Z",
        "project": project,
        "patchId": patch_id,
        "preconditions": {"projectBuild": "demo-build"},
        "files": [{"path": "HELLO.txt", "operation": "write", "bytes": len(payload), "sha256": digest}],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PATCH_MANIFEST.json", json.dumps(manifest))
        zf.writestr("payload/HELLO.txt", payload)


class ForgeF60R8Tests(unittest.TestCase):
    def test_version_authority(self) -> None:
        from ForgeVersion import VERSION, BUILD
        self.assertEqual(VERSION, "0.4.415-F60R415")
        self.assertEqual(BUILD, "FORGEPY-F60R415")

    def test_download_is_cataloged_then_explicitly_approved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            downloads = base / "Downloads"; downloads.mkdir()
            vault = base / "Vault"
            project = base / "Project"; project.mkdir(); write_contract(project)
            patch = downloads / "Demo_R8_RootPatch.zip"
            make_patch(patch)
            with env(FORGE_VAULT_ROOT=str(vault), FORGE_INTAKE_PATHS=str(downloads)):
                result = scan_downloads(force_stable=True, remove_source=True)
                self.assertEqual(result["ingested"][0]["state"], "CANDIDATE", result)
                self.assertEqual(counts_for_project("demo", "Demo"), (0, 0))
                available = available_for_project(project)
                self.assertEqual(len(available), 1, available)
                approved = approve_available_for_project(project, available[0]["intake_id"])
                self.assertEqual(approved["state"], "QUEUED", approved)
                self.assertTrue(approved["approved_utc"])
                self.assertTrue(Path(approved["approvalReceipt"]).is_file())
                self.assertEqual(counts_for_project("demo", "Demo"), (1, 0))
                staged = stage_for_project(project)
                self.assertEqual(staged["staged"], 1, staged)

    def test_incoming_patch_is_single_file_trusted_root_transport(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "Vault"
            project = base / "Project"; project.mkdir(); write_contract(project)
            incoming = project / "incoming.patch"
            make_patch(incoming, patch_id="DEMO-INCOMING-001")
            with env(FORGE_VAULT_ROOT=str(vault), FORGE_INTAKE_PATHS=str(base / "Downloads")):
                scanned = scan_roots((project,), force_stable=True, remove_source=True, trusted_roots=(project,))
                self.assertEqual(len(scanned["ingested"]), 1, scanned)
                self.assertEqual(scanned["ingested"][0]["state"], "QUEUED", scanned)
                self.assertFalse(incoming.exists())
                staged = stage_for_project(project)
                self.assertEqual(staged["staged"], 1, staged)
                self.assertFalse((project / "updates" / "inbox").exists())
                from VaultPatchEngine import apply_transport
                receipt = apply_transport(Path(staged["items"][0]["source"]), project)
                self.assertEqual(receipt["status"], "applied", receipt)
                self.assertEqual((project / "HELLO.txt").read_text(encoding="utf-8"), "hello-r8\n")

    def test_manual_root_drop_of_already_cataloged_download_counts_as_approval(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            downloads = base / "Downloads"; downloads.mkdir()
            vault = base / "Vault"
            project = base / "Project"; project.mkdir(); write_contract(project)
            source = downloads / "Demo_R8_RootPatch.zip"
            make_patch(source, patch_id="DEMO-MANUAL-001")
            original_bytes = source.read_bytes()
            with env(FORGE_VAULT_ROOT=str(vault), FORGE_INTAKE_PATHS=str(downloads)):
                first = scan_downloads(force_stable=True, remove_source=True)
                self.assertEqual(first["ingested"][0]["state"], "CANDIDATE", first)
                root_drop = project / "incoming.patch"
                root_drop.write_bytes(original_bytes)
                second = scan_roots((project,), force_stable=True, remove_source=True, trusted_roots=(project,))
                self.assertEqual(second["ingested"][0]["state"], "QUEUED", second)
                self.assertTrue(second["ingested"][0]["approved_utc"])
                self.assertFalse(root_drop.exists())


    def test_repo_hygiene_preserves_pending_incoming_patch(self) -> None:
        from PCCRepoHygiene import classify_root
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); write_contract(root)
            incoming = root / "incoming.patch"
            make_patch(incoming, patch_id="DEMO-HYGIENE-001")
            scan = classify_root(root)
            self.assertIn("incoming.patch", scan["pendingPatchTransports"], scan)
            self.assertNotIn("incoming.patch", scan["otherZip"], scan)

    def test_gui_exposes_safe_download_approval_and_immediate_watcher_scan(self) -> None:
        text = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn('"Approve Download…"', text)
        self.assertIn('"Check Downloads"', text)
        self.assertIn('vault_approve_available_for_project', text)
        self.assertIn('while not self._intake_stop.is_set()', text)
        self.assertIn('ForgePY update available', text)


if __name__ == "__main__":
    unittest.main()
