from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ForgePYVersion import BUILD, PRODUCT, VERSION
from ForgePYInternalGit import ensure as ensure_internal_git, push_snapshot, status as internal_status
from ForgePYSourceControl import status as source_status


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


class ForgePYF60R17Tests(unittest.TestCase):
    def test_identity(self) -> None:
        self.assertEqual(VERSION, "0.4.377-F60R377")
        self.assertEqual(BUILD, "FORGEPY-F60R377")
        self.assertEqual(PRODUCT, "ForgePY")

    def test_canonical_brand_assets(self) -> None:
        png = ROOT / "assets" / "branding" / "ForgePY.png"
        ico = ROOT / "assets" / "branding" / "ForgePY.ico"
        self.assertTrue(png.is_file())
        self.assertTrue(ico.is_file())
        self.assertGreater(png.stat().st_size, 100_000)
        self.assertEqual(ico.read_bytes()[:4], b"\x00\x00\x01\x00")
        text = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        tray = (APP / "VaultTray.py").read_text(encoding="utf-8")
        self.assertIn("apply_window_icon(self.window)", text)
        self.assertIn("ICON_ICO", tray)

    def test_canonical_module_facades_exist(self) -> None:
        names = (
            "ForgePYBrand.py", "ForgePYSettings.py", "ForgePYPaths.py", "ForgePYIntake.py",
            "ForgePYPatchEngine.py", "ForgePYSourceControl.py", "ForgePYHealth.py", "ForgePYTray.py",
        )
        for name in names:
            self.assertTrue((APP / name).is_file(), name)

    def test_source_control_workspace_is_primary_and_forgejo_optional(self) -> None:
        text = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn('("Source Control", "Source Control")', text)
        self.assertNotIn('("Forgejo", "Forgejo")', text)
        self.assertIn('"ForgeGit"', text)
        self.assertIn('"Forgejo Compatibility"', text)
        self.assertIn('"Select .patch…"', text)
        self.assertIn('"PROJECT CONTEXT"', text)

    def test_default_settings_make_internal_git_primary(self) -> None:
        from ForgePYSettings import defaults
        cfg = defaults()
        source = cfg["sourceControl"]
        self.assertTrue(source["internalGitEnabled"])
        self.assertEqual(source["defaultInternalGitRemote"], "forgepy-internal")
        self.assertIn("InternalGit", source["internalGitRoot"])
        self.assertEqual(cfg["schema"], "forgepy.settings.v1")

    def test_legacy_settings_normalize_to_forgepy_schema(self) -> None:
        from ForgePYSettings import SETTINGS_VERSION, load_settings, save_settings
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "legacy.settings.json"
            path.write_text(json.dumps({
                "schema": "vault.settings.v1",
                "version": "VAULT-SETTINGS-OLD",
                "sourceControl": {"internalGitEnabled": False},
            }), encoding="utf-8")
            with env(FORGEPY_SETTINGS_PATH=str(path)):
                cfg = load_settings()
                self.assertEqual(cfg["schema"], "forgepy.settings.v1")
                self.assertEqual(cfg["version"], SETTINGS_VERSION)
                self.assertFalse(cfg["sourceControl"]["internalGitEnabled"])
                save_settings(cfg)
                saved = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(saved["schema"], "forgepy.settings.v1")
                self.assertEqual(saved["version"], SETTINGS_VERSION)

    def test_internal_git_can_bind_and_snapshot_normal_git_repo(self) -> None:
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            project = base / "project"
            project.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "forgepy-test@example.invalid"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "ForgePY Test"], cwd=project, check=True)
            (project / "README.md").write_text("ForgePY internal git test\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "test"], cwd=project, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            settings = base / "settings.json"
            settings.write_text(json.dumps({
                "sourceControl": {
                    "internalGitEnabled": True,
                    "internalGitRoot": str(base / "InternalGit"),
                    "defaultInternalGitRemote": "forgepy-internal",
                }
            }), encoding="utf-8")
            with env(FORGEPY_SETTINGS_PATH=str(settings)):
                prepared = ensure_internal_git(project, "demo")
                self.assertEqual(prepared.returncode, 0, prepared.stdout)
                snap = push_snapshot(project, "demo")
                self.assertEqual(snap.returncode, 0, snap.stdout)
                istate = internal_status(project, "demo")
                self.assertTrue(istate["repositoryReady"], istate)
                self.assertTrue(istate["remoteConfigured"], istate)
                state = source_status(project)
                self.assertTrue(state["internalGitConfigured"], state)
                refs = subprocess.run(
                    ["git", "--git-dir", str(base / "InternalGit" / "demo.git"), "show-ref", "--verify", "refs/heads/main"],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
                )
                self.assertEqual(refs.returncode, 0, refs.stdout)

    def test_roadmap_records_next_twenty(self) -> None:
        text = (ROOT / "docs" / "NEXT_20_PASSES_F61_F80.md").read_text(encoding="utf-8")
        for pass_id in ("F61", "F65", "F66", "F80"):
            self.assertIn(pass_id, text)


if __name__ == "__main__":
    unittest.main()
