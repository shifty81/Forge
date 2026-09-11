from __future__ import annotations

import json
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import VaultDriveIndex
from ForgePYIntake import parse_canonical_patch_filename, canonical_patch_filename
from ForgePYVersion import VERSION, BUILD


class ForgePYF60R22Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION, "0.4.377-F60R377")
        self.assertEqual(BUILD, "FORGEPY-F60R377")

    def test_canonical_patch_filename_contract(self):
        meta = parse_canonical_patch_filename("Cortex__20260910__1.2.3.patch")
        self.assertEqual(meta["project"], "Cortex")
        self.assertEqual(meta["date"], "20260910")
        self.assertEqual(meta["version"], "1.2.3")
        self.assertEqual(canonical_patch_filename("ForgePY", "0.4.377-F60R377"), canonical_patch_filename("ForgePY", "0.4.377-F60R377"))
        self.assertFalse(parse_canonical_patch_filename("random_old_patch.patch"))

    def test_embedded_console_is_no_window_and_tray_notice_is_deduped(self):
        surface = (ROOT / "app" / "PCCSurfaceCommon.py").read_text(encoding="utf-8")
        gui = (ROOT / "app" / "ForgeGui.py").read_text(encoding="utf-8")
        start = surface.index("def _embedded_creationflags")
        excerpt = surface[start:start + 1800]
        self.assertIn("CREATE_NO_WINDOW", excerpt)
        self.assertNotIn("CREATE_NEW_CONSOLE", excerpt)
        self.assertIn("_tray_minimize_notice_sent", gui)
        self.assertIn("ForgePY is still running in the system tray", gui)

    def test_forgepy_has_dedicated_self_update_lane(self):
        gui = (ROOT / "app" / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn("def _start_forgepy_self_apply", gui)
        self.assertIn("ForgePY Control", gui)
        self.assertIn("Apply Approved Self Update", gui)
        self.assertIn("self._start_forgepy_self_apply", gui)

    def test_patch_review_is_actionable_across_projects(self):
        gui = (ROOT / "app" / "ForgeGui.py").read_text(encoding="utf-8")
        for label in ("Queue + Apply", "Archive Lineage", "Ignore", "Reveal"):
            self.assertIn(label, gui)
        intake = (ROOT / "app" / "VaultIntake.py").read_text(encoding="utf-8")
        self.assertIn('{"REVIEW", "CANDIDATE"}', intake)
        self.assertIn("Cortex vs", intake)

    def test_drive_catalog_indexes_everything_and_owns_nested_files(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            scan_root = base / "VaultDrive"
            project = scan_root / "ProjectA"
            nested = project / "crates" / "worker"
            nested.mkdir(parents=True)
            (project / "project.control.json").write_text(json.dumps({"schema":"project.control.v1","project":{"id":"ProjectA","name":"ProjectA"}}), encoding="utf-8")
            (project / "src").mkdir()
            source = project / "src" / "main.py"
            source.write_text("print('ok')\n", encoding="utf-8")
            (nested / "Cargo.toml").write_text("[package]\nname='worker'\nversion='0.1.0'\n", encoding="utf-8")
            loose = scan_root / "loose_notes.txt"
            loose.write_text("unassigned drive content", encoding="utf-8")

            old_db_path = VaultDriveIndex.db_path
            VaultDriveIndex.db_path = lambda: base / "drive_index.db"
            try:
                summary = VaultDriveIndex.scan(scan_root)
                entries = VaultDriveIndex.list_entries(scan_root, limit=1000)
                authorities = VaultDriveIndex.list_projects(scan_root, include_components=False)
            finally:
                VaultDriveIndex.db_path = old_db_path

            paths = {Path(str(row["path"])): row for row in entries}
            self.assertIn(source.resolve(), paths)
            self.assertIn(loose.resolve(), paths)
            self.assertEqual(Path(paths[source.resolve()]["ownerProjectRoot"]), project.resolve())
            self.assertEqual(len(authorities), 1, authorities)
            self.assertEqual(Path(authorities[0]["root"]), project.resolve())
            self.assertGreaterEqual(int(summary.get("entries") or 0), 5)


if __name__ == "__main__":
    unittest.main()
