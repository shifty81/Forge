from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ForgeGreen import certify_green, green_status
from ForgeProjectSource import declared_project_github, project_github
from ForgeSourceControl import _adopt_remote_history_if_unborn, command, status
from ForgeVersion import BUILD, VERSION
from PCCProjectDiscovery import discover_project_contract_data


class ForgeF60R6Tests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(root), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

    def test_version_authority(self):
        self.assertEqual(VERSION, "0.4.6-F60R6")
        self.assertEqual(BUILD, "FORGE-F60R6")

    def test_declared_github_is_available_before_remote_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "project.control.json").write_text(json.dumps({
                "project": {"id": "demo", "name": "Demo"},
                "sourceControl": {"github": {"remote": "origin", "webUrl": "https://github.com/shifty81/Forge"}},
            }), encoding="utf-8")
            declared = declared_project_github(root)
            self.assertEqual(declared["cloneUrl"], "https://github.com/shifty81/Forge.git")
            self.assertEqual(project_github(root)["webUrl"], "https://github.com/shifty81/Forge")

    def test_review_on_unborn_repository_is_not_head_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._git(root, "init", "-b", "main")
            (root / "new.txt").write_text("new\n", encoding="utf-8")
            cp = command(root, "review")
            self.assertEqual(cp.returncode, 0, cp.stdout)
            self.assertIn("no local commit yet", cp.stdout.lower())
            self.assertIn("new.txt", cp.stdout)
            self.assertNotIn("ambiguous argument 'HEAD'", cp.stdout)

    def test_unborn_worktree_can_adopt_remote_parent_without_replacing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seed = base / "seed"
            remote = base / "remote.git"
            local = base / "local"
            seed.mkdir(); local.mkdir()
            self._git(seed, "init", "-b", "main")
            self._git(seed, "config", "user.email", "test@example.com")
            self._git(seed, "config", "user.name", "Forge Test")
            (seed / "legacy.txt").write_text("legacy\n", encoding="utf-8")
            self._git(seed, "add", "-A"); self._git(seed, "commit", "-m", "legacy")
            subprocess.run(["git", "clone", "--bare", str(seed), str(remote)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
            self._git(local, "init", "-b", "main")
            (local / "forge.txt").write_text("forge\n", encoding="utf-8")
            self._git(local, "remote", "add", "origin", str(remote))
            messages, adopted = _adopt_remote_history_if_unborn(local, "origin", "main")
            self.assertTrue(adopted, messages)
            self.assertTrue((local / "forge.txt").is_file())
            self.assertFalse((local / "legacy.txt").exists())
            self.assertTrue(status(local)["hasHead"])
            review = command(local, "review")
            self.assertEqual(review.returncode, 0, review.stdout)
            self.assertIn("legacy.txt", review.stdout)
            self.assertIn("forge.txt", review.stdout)

    def test_generic_git_project_gets_green_commit_and_push_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._git(root, "init", "-b", "main")
            data = discover_project_contract_data(root)
            keys = {row["key"] for row in data["commands"]}
            self.assertIn("git.commit-green", keys)
            self.assertIn("git.push", keys)

    def test_green_authority_is_external_and_matches_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data:
            root = Path(tmp)
            old = __import__("os").environ.get("FORGE_ARTIFACT_CENTRAL_ROOT")
            __import__("os").environ["FORGE_ARTIFACT_CENTRAL_ROOT"] = str(Path(data) / "Artifacts")
            try:
                self._git(root, "init", "-b", "main")
                (root / "source.py").write_text("print('a')\n", encoding="utf-8")
                cert = certify_green(root)
                marker, match, path, _ = green_status(root)
                self.assertTrue(marker); self.assertTrue(match)
                self.assertFalse(str(path).startswith(str(root)))
                (root / "source.py").write_text("print('b')\n", encoding="utf-8")
                self.assertFalse(green_status(root)[1])
                self.assertEqual(cert["result"], "GREEN")
            finally:
                if old is None:
                    __import__("os").environ.pop("FORGE_ARTIFACT_CENTRAL_ROOT", None)
                else:
                    __import__("os").environ["FORGE_ARTIFACT_CENTRAL_ROOT"] = old

    def test_forge_contract_declares_canonical_github(self):
        data = json.loads((APP.parent / "project.control.json").read_text(encoding="utf-8"))
        self.assertEqual(data["sourceControl"]["github"]["webUrl"], "https://github.com/shifty81/Forge")
        self.assertEqual(data["sourceControl"]["github"]["remote"], "origin")


if __name__ == "__main__":
    unittest.main()
