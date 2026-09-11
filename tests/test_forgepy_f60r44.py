from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ForgePYVersion import VERSION, BUILD
from ForgePYSettings import defaults
from ForgeSourceControl import repository_tree, branch_graph, command as source_command
from ForgeGit import ensure, push_snapshot, verify, export_bundle, repository_path


class ForgePYF60R44Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION, "0.4.379-F60R379")
        self.assertEqual(BUILD, "FORGEPY-F60R379")

    def test_roadmap_contains_twenty_completed_passes(self):
        text = (ROOT / "docs" / "NEXT_20_PASSES_F71_F90.md").read_text(encoding="utf-8")
        for number in range(71, 91):
            self.assertIn(f"F{number}", text)
        self.assertGreaterEqual(text.count("COMPLETE"), 20)

    def test_forgegit_is_canonical_but_legacy_settings_remain_migratable(self):
        cfg = defaults()["sourceControl"]
        self.assertTrue(cfg["forgeGitEnabled"])
        self.assertEqual(cfg["defaultForgeGitRemote"], "forgegit")
        self.assertIn("ForgeGit", cfg["forgeGitRoot"])
        self.assertIn("internalGitEnabled", cfg)  # compatibility input only
        self.assertTrue((APP / "ForgeGit.py").is_file())
        self.assertTrue((APP / "ForgePYInternalGit.py").is_file())

    def test_gui_contains_visual_source_and_performance_surfaces(self):
        text = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        for token in (
            '"Branches / Tags"', '"Repository"', '"Rename"', '"Discard"',
            '"Verify ForgeGit"', '"Export Recovery Bundle"', '"Authority Matrix"',
            '"Repair / Rebind Source"', '"Route…"', '"Load More"',
            '"Performance Report"',
        ):
            self.assertIn(token, text)

    def test_patch_review_is_forgepy_owned_for_generic_projects(self):
        text = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn("_start_universal_project_apply", text)
        self.assertIn("run_full_after=True", text)
        intake = (APP / "VaultIntake.py").read_text(encoding="utf-8")
        self.assertIn("def retarget_review_item", intake)

    def test_utf8_embedded_environment_is_explicit(self):
        for name in ("PCCOperationHost.py", "PCCSurfaceCommon.py", "ForgeGit.py"):
            text = (APP / name).read_text(encoding="utf-8")
            self.assertIn("PYTHONIOENCODING", text, name)

    @unittest.skipUnless(shutil.which("git"), "git unavailable")
    def test_forgegit_branch_tree_snapshot_verify_and_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            project = base / "project"; project.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "forgepy-test@example.invalid"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "ForgePY Test"], cwd=project, check=True)
            (project / "project.control.json").write_text(json.dumps({"project":{"id":"demo"}}), encoding="utf-8")
            (project / "a.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=project, check=True, stdout=subprocess.DEVNULL)
            settings = base / "settings.json"
            settings.write_text(json.dumps({"sourceControl":{"forgeGitEnabled":True,"forgeGitRoot":str(base/"ForgeGit"),"defaultForgeGitRemote":"forgegit"}}), encoding="utf-8")
            old = __import__('os').environ.get('FORGEPY_SETTINGS_PATH')
            __import__('os').environ['FORGEPY_SETTINGS_PATH'] = str(settings)
            try:
                self.assertEqual(ensure(project,"demo").returncode,0)
                self.assertEqual(push_snapshot(project,"demo").returncode,0)
                self.assertEqual(verify("demo").returncode,0)
                bundle=base/"demo.bundle"
                self.assertEqual(export_bundle("demo",bundle).returncode,0)
                self.assertTrue(bundle.is_file())
                rows=repository_tree(project,100)
                self.assertTrue(any(r["path"]=="a.txt" for r in rows))
                self.assertIn("base", branch_graph(project,10))
                self.assertEqual(source_command(project,"create-branch","feature/test","HEAD").returncode,0)
                self.assertEqual(source_command(project,"switch-branch","main").returncode,0)
            finally:
                if old is None:
                    __import__('os').environ.pop('FORGEPY_SETTINGS_PATH',None)
                else:
                    __import__('os').environ['FORGEPY_SETTINGS_PATH']=old

    def test_gap_audit_is_explicit_about_remaining_work(self):
        text=(ROOT/"docs"/"F71_F90_GAP_AUDIT.md").read_text(encoding="utf-8")
        for gap in ("Native Windows drag/drop intake", "Incremental D:\\ watcher", "Visual conflict resolver", "Release installer/signing"):
            self.assertIn(gap,text)


if __name__ == "__main__":
    unittest.main()
