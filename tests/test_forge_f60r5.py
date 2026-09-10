from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
import sys
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ForgeProjectSource import normalize_github_repo
from ForgeUniversalTooling import capability_row
from ForgeVersion import BUILD, VERSION
from PCCProjectDiscovery import discover_project_contract_data
from VaultIntake import _promote_verified


class ForgeF60R5Tests(unittest.TestCase):
    def test_version_authority(self):
        self.assertEqual(VERSION, "0.4.8-F60R8")
        self.assertEqual(BUILD, "FORGE-F60R8")

    def test_github_url_normalization(self):
        clone, web = normalize_github_repo("shifty81/Havenwild")
        self.assertEqual(clone, "https://github.com/shifty81/Havenwild.git")
        self.assertEqual(web, "https://github.com/shifty81/Havenwild")
        self.assertEqual(normalize_github_repo("git@github.com:shifty81/Forge.git")[1], "https://github.com/shifty81/Forge")

    def test_destination_volume_promotion_is_copy_verify_then_local_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "source" / "patch.zip"
            dst = root / "artifact" / "patch.zip"
            src.parent.mkdir()
            src.write_bytes(b"forge-cross-volume-safe")
            digest = hashlib.sha256(src.read_bytes()).hexdigest()
            _promote_verified(src, dst, digest, remove_source=True)
            self.assertTrue(dst.is_file())
            self.assertFalse(src.exists())
            self.assertEqual(hashlib.sha256(dst.read_bytes()).hexdigest(), digest)

    def test_command_registry_project_pcc_outranks_generic_rust_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Demo"
            control = root / "tools" / "control"
            control.mkdir(parents=True)
            (root / "Cargo.toml").write_text('[workspace]\nmembers=[]\n', encoding="utf-8")
            (root / "DemoTools.cmd").write_text("@echo off\n", encoding="utf-8")
            (control / "ProjectCommandRegistry.ps1").write_text(
                "@(\n"
                "@{ Id='1'; Key='build.all'; Label='Build all'; Kind='Build'; Category='builds'; Args=@('all') }\n"
                "@{ Id='2'; Key='validation.full-quality-gate'; Label='Full quality gate'; Kind='BuiltinQualityGate'; Category='validation'; Args=@() }\n"
                ")\n",
                encoding="utf-8",
            )
            (control / "DemoTools.ps1").write_text(
                "param([string]$Command='menu')\n$Commands=@(& (Join-Path $PSScriptRoot 'ProjectCommandRegistry.ps1'))\n",
                encoding="utf-8",
            )
            data = discover_project_contract_data(root)
            by_key = {c["key"]: c for c in data["commands"]}
            self.assertIn("gate.full", by_key)
            self.assertIn("build.native", by_key)
            self.assertEqual(by_key["gate.full"]["program"], "powershell")
            self.assertIn("-Command", by_key["gate.full"]["args"])
            self.assertEqual(data["_pccDiscovery"]["provider"], "tools/control/DemoTools.ps1")

    def test_capability_matrix_sees_generic_rust_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text('[workspace]\nmembers=[]\n', encoding="utf-8")
            row = capability_row(root)
            self.assertTrue(row["build"])
            self.assertTrue(row["full"])

    def test_periodic_git_probes_are_no_window_on_windows(self):
        text = (APP / "PCCAutoAdapter.py").read_text(encoding="utf-8")
        self.assertIn("CREATE_NO_WINDOW", text)
        self.assertIn("startupinfo=startupinfo", text)
        common = (APP / "PCCSurfaceCommon.py").read_text(encoding="utf-8")
        self.assertIn("def _quiet_creationflags", common)
        self.assertIn("creationflags=self._quiet_creationflags()", common)

    def test_streaming_adapter_normalizes_unicode_output(self):
        text = (APP / "PCCAutoAdapter.py").read_text(encoding="utf-8")
        self.assertIn("def _normalize_stdio", text)
        self.assertIn("_normalize_stdio()", text)
        self.assertIn('encoding="utf-8", errors="replace"', text)

    def test_middle_command_pages_are_scrollable_and_github_link_exists(self):
        text = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn("def _make_scrollable_page", text)
        self.assertIn('"Source Control"', text)
        self.assertIn('"Tooling"', text)
        self.assertIn('"Open GitHub"', text)
        self.assertIn("_clone_project_from_github", text)

    def test_health_refresh_cannot_overlap(self):
        text = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn("_active_health_scan_running", text)
        self.assertIn('("active-health-idle", root)', text)


if __name__ == "__main__":
    unittest.main()
