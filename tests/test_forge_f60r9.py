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

from ForgeVersion import VERSION, BUILD
from PCCAutoAdapter import _count_updates
from PCCRepoHygiene import classify_root
from PCCSurfaceCommon import ProjectRegistry
from VaultIntake import (
    _connect,
    approve_available_for_project,
    available_for_project,
    counts_for_project,
    list_items,
    scan_downloads,
    scan_roots,
    stage_for_project,
)


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
    data = {
        "schema": "forge.project.v1",
        "project": {"id": "demo", "name": "Demo", "kind": "python", "build": build, "version": "2.0"},
        "commands": [],
    }
    (root / "project.control.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_patch(path: Path, *, patch_id: str, build: str = "B2", schema: str = "forge.patch.v1", project: str = "Demo") -> None:
    payload = b"r9\n"
    digest = hashlib.sha256(payload).hexdigest()
    manifest = {
        "schema": schema,
        "engine": "forge-universal",
        "createdUtc": "2026-09-10T10:00:00Z",
        "project": project,
        "patchId": patch_id,
        "preconditions": {"projectBuild": build},
        "files": [{"path": "r9.txt", "operation": "write", "bytes": len(payload), "sha256": digest}],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PATCH_MANIFEST.json", json.dumps(manifest))
        zf.writestr("payload/r9.txt", payload)


class ForgeF60R9Tests(unittest.TestCase):
    def test_forge_project_contract_declares_single_file_update_policy(self) -> None:
        from ForgeContracts import validate_project_contract
        data = json.loads((ROOT / "project.control.json").read_text(encoding="utf-8"))
        checked = validate_project_contract(data)
        self.assertEqual(checked["incoming"], "incoming.patch")
        self.assertEqual(checked["patchSchema"], "forge.patch.v1")
        self.assertFalse(data["updates"]["downloadsAutoQueue"])

    def test_version_authority(self) -> None:
        self.assertEqual(VERSION, "0.4.377-F60R377")
        self.assertEqual(BUILD, "FORGEPY-F60R377")

    def test_historical_named_root_patch_is_lineage_not_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); project = base / "Demo"; project.mkdir(); write_contract(project)
            patch = project / "Demo_Old_RootPatch.zip"; make_patch(patch, patch_id="DEMO-OLD-001", build="B1")
            with env(FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(base / "Downloads")):
                result = scan_roots((project,), force_stable=True, remove_source=True, trusted_roots=(project,))
                self.assertEqual(result["errors"], [], result)
                self.assertEqual(result["ingested"][0]["state"], "LINEAGE", result)
                self.assertEqual(counts_for_project("demo", "Demo"), (0, 0))
                self.assertFalse((project / "updates" / "inbox").exists())
                self.assertIn("lineage", result["ingested"][0]["vault_path"].replace("\\", "/"))

    def test_incoming_patch_must_match_current_build_before_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); project = base / "Demo"; project.mkdir(); write_contract(project, "B2")
            patch = project / "incoming.patch"; make_patch(patch, patch_id="DEMO-BADBASE-001", build="B1")
            with env(FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(base / "Downloads")):
                result = scan_roots((project,), force_stable=True, remove_source=True, trusted_roots=(project,))
                self.assertEqual(len(result["errors"]), 1, result)
                self.assertEqual(counts_for_project("demo", "Demo"), (0, 0))
                rows = list_items(project="Demo")
                self.assertEqual(rows[0]["state"], "LINEAGE", rows)
                self.assertIn("base-mismatch", rows[0]["vault_path"].replace("\\", "/"))

    def test_download_discovery_never_queues_even_when_current(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); downloads = base / "Downloads"; downloads.mkdir(); project = base / "Demo"; project.mkdir(); write_contract(project)
            patch = downloads / "Demo_Current_RootPatch.zip"; make_patch(patch, patch_id="DEMO-CURRENT-001")
            with env(FORGE_PROJECT_REGISTRY=str(base / "registry.json"), FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(downloads)):
                ProjectRegistry().register(project, make_active=True)
                result = scan_downloads(force_stable=True, remove_source=True)
                self.assertEqual(result["ingested"][0]["state"], "CANDIDATE", result)
                self.assertEqual(counts_for_project("demo", "Demo"), (0, 0))
                self.assertEqual(stage_for_project(project)["staged"], 0)
                self.assertFalse((project / "updates" / "inbox").exists())

    def test_registered_old_download_goes_to_lineage_not_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); downloads = base / "Downloads"; downloads.mkdir(); project = base / "Demo"; project.mkdir(); write_contract(project, "B2")
            patch = downloads / "Demo_Old_RootPatch.zip"; make_patch(patch, patch_id="DEMO-HIST-001", build="B1")
            with env(FORGE_PROJECT_REGISTRY=str(base / "registry.json"), FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(downloads)):
                ProjectRegistry().register(project, make_active=True)
                result = scan_downloads(force_stable=True, remove_source=True)
                self.assertEqual(result["ingested"][0]["state"], "LINEAGE", result)
                self.assertEqual(counts_for_project("demo", "Demo"), (0, 0))
                self.assertEqual(available_for_project(project), [])
                self.assertIn("base-mismatch", result["ingested"][0]["vault_path"].replace("\\", "/"))

    def test_only_explicit_approval_creates_executable_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); downloads = base / "Downloads"; downloads.mkdir(); project = base / "Demo"; project.mkdir(); write_contract(project)
            patch = downloads / "Demo_Current_RootPatch.zip"; make_patch(patch, patch_id="DEMO-APPROVE-001")
            with env(FORGE_PROJECT_REGISTRY=str(base / "registry.json"), FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(downloads)):
                ProjectRegistry().register(project, make_active=True)
                scan_downloads(force_stable=True, remove_source=True)
                candidates = available_for_project(project)
                self.assertEqual(len(candidates), 1, candidates)
                approved = approve_available_for_project(project, candidates[0]["intake_id"])
                self.assertEqual(approved["state"], "QUEUED", approved)
                self.assertTrue(approved["approved_utc"])
                self.assertEqual(counts_for_project("demo", "Demo"), (1, 0))
                staged = stage_for_project(project)
                self.assertEqual(staged["staged"], 1, staged)
                self.assertEqual(staged["items"][0]["projectInbox"], "")
                self.assertFalse((project / "updates" / "inbox").exists())

    def test_pre_f60r9_unauthorized_queue_is_demoted_to_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); downloads = base / "Downloads"; downloads.mkdir(); project = base / "Demo"; project.mkdir(); write_contract(project)
            patch = downloads / "Demo_Current_RootPatch.zip"; make_patch(patch, patch_id="DEMO-STALEQUEUE-001")
            with env(FORGE_PROJECT_REGISTRY=str(base / "registry.json"), FORGE_VAULT_ROOT=str(base / "Vault"), FORGE_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), FORGE_INTAKE_PATHS=str(downloads)):
                ProjectRegistry().register(project, make_active=True)
                scan_downloads(force_stable=True, remove_source=True)
                row = list_items(project="Demo")[0]
                db = _connect()
                try:
                    db.execute("UPDATE intake_items SET state='QUEUED',approved_utc='',approved_root='' WHERE intake_id=?", (row["intake_id"],))
                    db.commit()
                finally:
                    db.close()
                self.assertEqual(counts_for_project("demo", "Demo"), (0, 0))
                repaired = list_items(project="Demo")[0]
                self.assertEqual(repaired["state"], "LINEAGE", repaired)
                self.assertIn("lineage", repaired["vault_path"].replace("\\", "/"))

    def test_generic_health_does_not_count_legacy_project_inbox_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); write_contract(root)
            inbox = root / "updates" / "inbox"; inbox.mkdir(parents=True)
            for i in range(50):
                (inbox / f"old-{i:02d}.zip").write_bytes(b"old")
                (inbox / f"old-{i:02d}.zip.sha256").write_text("0" * 64, encoding="ascii")
            self.assertEqual(_count_updates(root, {"project": {"id": "demo", "name": "Demo"}}), (0, 0))

    def test_repo_hygiene_only_marks_incoming_patch_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); write_contract(root)
            old = root / "Demo_Old_RootPatch.zip"; make_patch(old, patch_id="DEMO-OLD-002", build="B1")
            incoming = root / "incoming.patch"; make_patch(incoming, patch_id="DEMO-INCOMING-002")
            scan = classify_root(root)
            self.assertEqual(scan["pendingPatchTransports"], ["incoming.patch"], scan)
            self.assertIn(old.name, scan["otherZip"], scan)


if __name__ == "__main__":
    unittest.main()
