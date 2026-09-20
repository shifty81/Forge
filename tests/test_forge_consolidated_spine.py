"""Functional consolidation regression fixtures; no external GitHub or D: access."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ForgeProjectSource import (clone_repository, matching_local_remote,
                                normalize_github_repo, planned_clone_destination)
from VaultBuildIdentity import build_identity
from ForgeUnifiedCli import main as cli_main


class ConsolidatedSpineTests(unittest.TestCase):
    def test_owner_qualified_paths_do_not_collide(self):
        with tempfile.TemporaryDirectory() as d:
            a = planned_clone_destination("alice/Engine", Path(d))
            b = planned_clone_destination("bob/Engine", Path(d))
            self.assertNotEqual(a, b)
            self.assertEqual(a, Path(d) / "alice" / "Engine")

    def test_ambiguous_urls_rejected(self):
        bad = ("https://github.com/one/two/extra", "https://github.com/one/two?token=x",
               "http://github.com/one/two", "https://evil.com/one/two",
               "https://user:password@github.com/one/two", "../two", "one/..",
               "one/CON", "one/two#fragment")
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError):
                normalize_github_repo(text)

    def test_existing_matching_checkout_reused_only_when_real_remote_matches(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "same" / "project"
            (target / ".git").mkdir(parents=True)
            response = subprocess.CompletedProcess([], 0, "origin https://github.com/same/project.git (fetch)\n", "")
            with patch("ForgeProjectSource._run", return_value=response) as cmd:
                row = clone_repository("same/project", projects_root=root)
                self.assertTrue(row["alreadyPresent"])
                self.assertEqual(row["root"], str(target))
                self.assertNotIn("clone", str(cmd.call_args))
            wrong = subprocess.CompletedProcess([], 0, "origin https://github.com/other/project.git (fetch)\n", "")
            with patch("ForgeProjectSource._run", return_value=wrong) as cmd:
                with self.assertRaisesRegex(RuntimeError, "no matching GitHub remote"):
                    clone_repository("same/project", projects_root=root)
                self.assertNotIn("clone", str(cmd.call_args))

    def test_legacy_flat_checkout_reused_if_its_git_remote_matches(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "project" / ".git").mkdir(parents=True)
            response = subprocess.CompletedProcess([], 0, "origin git@github.com:same/project.git (fetch)\n", "")
            with patch("ForgeProjectSource._run", return_value=response):
                row = clone_repository("same/project", projects_root=root)
            self.assertTrue(row["alreadyPresent"])
            self.assertEqual(row["root"], str(root / "project"))

    def test_passive_version_parser_does_not_execute_python(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "app").mkdir()
            marker = root / "PWNED"
            (root / "app" / "ForgePYVersion.py").write_text(
                "VERSION = '9.8'\nBUILD = 'B123'\nfrom pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('executed')\n", encoding="utf-8")
            row = build_identity(root)
            self.assertEqual(row["projectVersion"], "9.8")
            self.assertEqual(row["projectBuild"], "B123")
            self.assertFalse(marker.exists())

    def test_failed_patch_queue_returns_nonzero(self):
        with patch("ForgeUnifiedCli.vault.queue_patch", return_value={"ok": False, "error": "not a patch"}):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = cli_main(["patch", "queue", "nonexistent.patch"])
        self.assertEqual(rc, 7)

    def test_cli_uses_existing_vault_scan_and_persists_same_catalog(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "scan"; source.mkdir()
            (source / "app").mkdir()
            (source / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (source / "app" / "demo.py").write_text("pass\n", encoding="utf-8")
            state = Path(d) / "state"
            with patch.dict(os.environ, {"FORGEPY_DATA_ROOT": str(state),
                                              "FORGEPY_VAULT_ROOT": str(state / "Library")}):
                with contextlib.redirect_stdout(io.StringIO()) as buf, contextlib.redirect_stderr(io.StringIO()):
                    rc = cli_main(["--json", "vault", "scan", "--scan-root", str(source), "--max-dirs", "100"])
                output = json.loads(buf.getvalue())
                self.assertEqual(rc, 0)
                self.assertTrue((state / "Library" / "catalog" / "drive_index.db").is_file())
                self.assertGreaterEqual(output["files"], 2)
                with contextlib.redirect_stdout(io.StringIO()) as buf:
                    self.assertEqual(cli_main(["--json", "vault", "catalog-status"]), 0)
                self.assertEqual(json.loads(buf.getvalue())["root"], str(source))

    def test_internal_service_error_emits_failure_not_success(self):
        from types import SimpleNamespace
        from ForgeUnifiedServices import ForgeOperationService
        from ForgeOperationEnvelope import OperationTranscript
        transcript = OperationTranscript("demo", "artifacts.list")
        emitted = []
        with tempfile.TemporaryDirectory() as d:
            with patch("ForgeArtifactIndex.search", side_effect=TypeError("bad schema")):
                row = ForgeOperationService()._direct(Path(d), SimpleNamespace(project_id="demo"),
                                                       "artifacts.list", transcript, emitted.append)
        self.assertFalse(row["ok"])
        self.assertEqual(row["returncode"], 8)
        self.assertEqual(emitted[-1]["event_type"], "operation.failed")
        self.assertFalse(any(x["event_type"] == "operation.result" for x in emitted))

    def test_package_manifest_includes_rust_binary_sources(self):
        import sys
        from pathlib import Path
        tools = str(Path(__file__).resolve().parents[1] / "tools")
        with patch.object(sys, "path", [tools, *sys.path]):
            from BuildForgePYManifest import _files
            paths = {row["path"] for row in _files()}
        self.assertIn("native/forge-rs/src/bin/forge_tool.rs", paths)

    def test_unavailable_scan_root_is_nonzero_and_does_not_create_it(self):
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d) / "NOT_PRESENT"
            with contextlib.redirect_stderr(io.StringIO()):
                rc = cli_main(["vault", "scan", "--scan-root", str(missing)])
            self.assertEqual(rc, 4)
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
