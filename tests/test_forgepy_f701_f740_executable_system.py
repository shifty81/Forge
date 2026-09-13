#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class ExecutableSystemTests(unittest.TestCase):
    def test_candidate_identity_is_f740(self) -> None:
        from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
        self.assertEqual(DISPLAY_VERSION, "0.5.0-candidate.797")
        self.assertEqual(DISPLAY_BUILD, "FORGEPY-F797")

    def test_nuitka_build_is_onedir_and_includes_dynamic_modules(self) -> None:
        text = (APP / "ForgeStandaloneBuild.py").read_text(encoding="utf-8")
        self.assertIn('"--standalone"', text)
        self.assertNotIn('"--onefile"', text)
        self.assertIn("def dynamic_modules", text)
        self.assertIn("--include-module=", text)

    def test_windows_file_metadata_tracks_candidate(self) -> None:
        text = (APP / "ForgeStandaloneBuild.py").read_text(encoding="utf-8")
        self.assertIn('NUMERIC_FILE_VERSION = "0.5.0.741"', text)
        self.assertIn("--file-version=", text)
        self.assertIn("--product-version=", text)

    def test_legacy_single_exe_updater_is_disabled(self) -> None:
        text = (APP / "ForgeSelfUpdateRuntime.py").read_text(encoding="utf-8")
        self.assertIn("mixed-version install", text)
        self.assertIn("ForgeSelfMaintenance", text)
        self.assertIn(".forgeupdate", text)

    def test_distribution_build_is_clean_and_bounded(self) -> None:
        exe = (APP / "ForgeExeBuild.py").read_text(encoding="utf-8")
        self.assertIn("shutil.rmtree(build_parent)", exe)
        self.assertIn("timeout=14400", exe)
        installer = (APP / "ForgeExecutableSystem.py").read_text(encoding="utf-8")
        self.assertIn("timeout=1800", installer)

    def test_inno_script_has_standard_and_portable_modes(self) -> None:
        text = (APP / "ForgeExecutableSystem.py").read_text(encoding="utf-8")
        self.assertIn("Standard install (recommended)", text)
        self.assertIn("Portable install", text)
        self.assertIn("Uninstallable={code:IsNotPortable}", text)
        self.assertIn(".forgepy-portable", text)

    def test_application_update_bundle_roundtrip(self) -> None:
        from ForgeExecutableSystem import build_update_bundle
        from ForgeSelfMaintenance import prepare_patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "dist" / "ForgePY-InstalledImage"
            image.mkdir(parents=True)
            (image / "ForgePY.exe").write_bytes(b"fake-exe")
            (image / "companion.dll").write_bytes(b"fake-dll")
            bundle = build_update_bundle(root, image)
            bundle_path = Path(bundle["path"])
            self.assertEqual(bundle_path.suffix, ".forgeupdate")
            with zipfile.ZipFile(bundle_path) as archive:
                self.assertIn("FORGEPY_UPDATE_MANIFEST.json", archive.namelist())
                self.assertIn("image/ForgePY.exe", archive.namelist())

            current = root / "PortableForgePY"
            current.mkdir()
            (current / "ForgePY.exe").write_bytes(b"old-exe")
            (current / ".forgepy-portable").write_text("portable\n", encoding="utf-8")
            (current / "Data").mkdir()
            (current / "Data" / "settings.json").write_text("{}", encoding="utf-8")
            plan = prepare_patch(bundle_path, current, approved=True, mode="portable")
            staged = Path(plan["stagedRoot"])
            self.assertTrue((staged / "ForgePY.exe").is_file())
            self.assertFalse(str(staged).casefold().startswith(str(current).casefold()))

    def test_packaged_build_rejects_source_transport(self) -> None:
        from ForgeSelfMaintenance import prepare_patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            current = root / "ForgePY"
            current.mkdir()
            (current / "ForgePY.exe").write_bytes(b"exe")
            patch = root / "x.patch"
            patch.write_text("test", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "requires a \\.forgeupdate"):
                prepare_patch(patch, current, approved=True, mode="portable")

    def test_portable_promotion_preserves_data(self) -> None:
        text = (APP / "ForgeSelfMaintenance.py").read_text(encoding="utf-8")
        self.assertIn("$oldData = Join-Path $rollback 'Data'", text)
        self.assertIn("Move-Item -Force $oldData $newData", text)
        self.assertIn("tempfile.gettempdir()", text)

    def test_navigation_is_latest_request_wins(self) -> None:
        text = (APP / "ForgeNavigationRuntime.py").read_text(encoding="utf-8")
        self.assertIn("after_cancel", text)
        self.assertIn("_forge_nav_generation", text)
        self.assertIn("requested == current", text)

    def test_quickbar_is_atomic(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        start = text.index("def render_quickbar")
        end = text.index("def build_quick_actions", start)
        block = text[start:end]
        self.assertIn("old_row = getattr", block)
        self.assertIn("host.pack(fill=\"x\", expand=True)", block)
        self.assertNotIn("for child in host.winfo_children()", block)

    def test_unified_cli_exposes_executable_lane(self) -> None:
        text = (APP / "ForgeUnifiedCli.py").read_text(encoding="utf-8")
        self.assertIn('sub.add_parser("executable")', text)
        self.assertIn('if ns.group == "executable":', text)
        root_cmd = (ROOT / "Forge.cmd").read_text(encoding="utf-8")
        self.assertIn("executable", root_cmd)


if __name__ == "__main__":
    unittest.main()
