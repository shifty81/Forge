from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import VaultIntake
import PCCRepoHygiene
from VaultSettings import defaults
from ForgePYVersion import VERSION, BUILD


class ForgePYF60R63Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION, "0.4.379-F60R379")
        self.assertEqual(BUILD, "FORGEPY-F60R379")

    def test_nonpatch_auto_archive_is_off_by_default(self):
        self.assertFalse(defaults()["intake"]["archiveNonPatchArtifacts"])

    def test_download_scanner_never_moves_nonpatch_content(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ordinary = root / "report.zip"
            ordinary.write_bytes(b"ordinary non-patch payload")
            with patch.object(VaultIntake, "looks_like_patch", return_value=False), \
                 patch.object(VaultIntake, "PATCH_NAME_RE") as name_re:
                name_re.search.return_value = None
                result = VaultIntake.scan_roots([root], force_stable=True, remove_source=True)
            self.assertTrue(ordinary.is_file())
            self.assertEqual(result["ingested"], [])
            self.assertEqual(result["artifacts"], [])
            self.assertTrue(any("patch-only" in row["reason"] for row in result["skipped"]))

    def test_manual_picker_can_approve_patch_already_moved_by_watcher(self):
        missing = Path(r"C:\Users\Example\Downloads\ForgePY__20260911__0.4.379-F60R379.patch")
        item = {
            "intake_id": "candidate-1",
            "original_path": str(missing),
            "sha256": "abc",
            "state": "CANDIDATE",
            "target_project": "forgepy",
            "manifest": {},
            "vault_path": "D:/Vault/fake.patch",
        }
        approved = {"intake_id": "candidate-1", "state": "QUEUED"}
        with patch.object(VaultIntake, "list_items", return_value=[item]), \
             patch.object(VaultIntake, "_queue_existing_for_project", return_value=approved) as queue:
            out = VaultIntake.approve_manual_patch_for_project(Path.cwd(), missing)
        self.assertEqual(out["state"], "QUEUED")
        queue.assert_called_once()

    def test_activation_hygiene_retains_nonpatch_artifacts(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "DebugBundle.zip").write_bytes(b"debug")
            with patch.object(PCCRepoHygiene, "ensure_local_git_excludes", return_value=[]), \
                 patch.object(PCCRepoHygiene, "_artifact_root", return_value=root / ".artifacts"):
                result = PCCRepoHygiene.prepare(root, apply=True)
            self.assertTrue((root / "DebugBundle.zip").exists())
            self.assertEqual(result["moved"], 0)


if __name__ == "__main__":
    unittest.main()
