#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class ForgePYF450F455StabilizationTests(unittest.TestCase):
    def test_source_authority_keeps_public_branch_api(self) -> None:
        from ForgeSourceAuthority import matrix, safe_branch_name
        self.assertEqual(safe_branch_name(" feature ^ branch "), "feature---branch")
        self.assertEqual(matrix(head="abc", github="abc")["state"], "SYNC")

    def test_browser_duplicate_patch_name_keeps_project_identity(self) -> None:
        if not (APP / "VaultIntake.py").exists():
            self.skipTest("overlay-only staging; canonical VaultIntake is supplied by the base ForgePY tree")
        from ForgePYIntake import parse_canonical_patch_filename
        parsed = parse_canonical_patch_filename("ForgePY__20260912__F455 (12).patch")
        self.assertEqual(parsed.get("project"), "ForgePY")
        self.assertEqual(parsed.get("date"), "20260912")
        self.assertEqual(parsed.get("version"), "F455")

    def test_facade_patches_vault_parser_and_resolver(self) -> None:
        if not (APP / "VaultIntake.py").exists():
            self.skipTest("overlay-only staging; canonical VaultIntake is supplied by the base ForgePY tree")
        import ForgePYIntake
        import VaultIntake
        self.assertIs(VaultIntake.parse_canonical_patch_filename, ForgePYIntake.parse_canonical_patch_filename)
        self.assertIs(VaultIntake.resolve_patch_target, ForgePYIntake.resolve_patch_target)

    def test_runtime_compatibility_module_is_present(self) -> None:
        import ForgeRuntimeCompatibility as compat
        self.assertEqual(compat.COMPAT_VERSION, "FORGEPY-RUNTIME-COMPAT-F700")

    def test_drive_census_has_disabled_watcher_guard(self) -> None:
        text = (APP / "ForgeDriveCensus.py").read_text(encoding="utf-8")
        self.assertIn("driveWatcher", text)
        self.assertIn('"skipped": True', text)


if __name__ == "__main__":
    unittest.main()
