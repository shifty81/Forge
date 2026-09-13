#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class CorrectnessHardeningTests(unittest.TestCase):
    def test_protocol_does_not_require_forgepy_owned_patch_services_from_project(self) -> None:
        from ForgeProjectProtocol import integration_grade
        grade = integration_grade([
            "project.status", "project.health", "project.self-test", "gate.full",
            "build.default", "run.default", "diagnostics.bundle",
        ], audit_current=True, handoffs_current=True)
        self.assertNotIn("patch.queue", grade["standardMissing"])
        self.assertNotIn("source.status", grade["standardMissing"])
        self.assertIn("patch.queue", grade["forgePyCapabilities"])
        self.assertEqual(grade["grade"], "STANDARDIZED")  # test.default still certification-only

    def test_configured_git_binary_is_honored(self) -> None:
        import ForgeStatusCache as cache
        fake = types.ModuleType("ForgePYSettings")
        fake.load_settings = lambda: {"sourceControl": {"gitBinary": __file__}}
        with mock.patch.dict(sys.modules, {"ForgePYSettings": fake}):
            value = cache.git_binary()
        self.assertEqual(Path(value).resolve(), Path(__file__).resolve())

    def test_workspace_scan_read_results_are_generation_keyed_and_coordinated(self) -> None:
        text = (APP / "ForgeWorkspaceSurface.py").read_text(encoding="utf-8")
        self.assertIn("_forge_workspace_scan_results", text)
        self.assertIn("_forge_workspace_read_results", text)
        self.assertIn("COORDINATOR.run_scan", text)
        self.assertIn("ForgeWorkspaceFileSave", text)
        self.assertNotIn("_forge_workspace_scan_result = None", text)
        self.assertNotIn("_forge_workspace_read_result = None", text)

    def test_project_background_results_are_root_or_generation_scoped(self) -> None:
        text = (APP / "ForgeProjectInteractionPerformance.py").read_text(encoding="utf-8")
        self.assertIn("_forge_hygiene_results", text)
        self.assertIn("_forge_activation_results", text)
        self.assertIn("_forge_handoff_results", text)
        self.assertIn("public registry fallback", text)
        self.assertIn("_github_details_from_status", text)

    def test_backend_generic_status_uses_fast_in_process_path(self) -> None:
        text = (APP / "ForgeBackendCapabilityPatch.py").read_text(encoding="utf-8")
        self.assertIn('mode in {"auto-contract", "forgepy-adapter"}', text)
        self.assertIn("fast_auto_status_payload", text)
        self.assertIn("BackendClient.status = status", text)

    def test_operation_transcript_and_output_are_bounded(self) -> None:
        from ForgeOperationEnvelope import OperationTranscript
        tx = OperationTranscript("p", "build.default", event_limit=100)
        for index in range(250):
            tx.emit("output", str(index))
        out = tx.finish(ok=True)
        self.assertLessEqual(len(out["events"]), 100)
        self.assertGreater(out["eventsDropped"], 0)
        service = (APP / "ForgeUnifiedServices.py").read_text(encoding="utf-8")
        self.assertIn("deque(maxlen=OUTPUT_TAIL_LIMIT)", service)
        self.assertIn("linesDropped", service)

    def test_patch_apply_preflights_whole_batch_and_creates_checkpoint(self) -> None:
        text = (APP / "PCCOperationHost.py").read_text(encoding="utf-8")
        self.assertIn("mixes ForgePY-universal and project-native transports", text)
        self.assertIn("Recovery checkpoint created before mutation", text)
        self.assertIn("GATE_FAILED_RECOVERY_AVAILABLE", text)
        self.assertIn("restore_checkpoint", text)
        self.assertNotIn("_universal_apply_staged", text)

    def test_checkpoint_restores_touched_files(self) -> None:
        import ForgePatchCheckpoint as checkpoint
        fake_engine = types.ModuleType("ForgePYPatchEngine")
        fake_engine.validate_transport = lambda source: {
            "sha256": "abc",
            "files": [{"path": "src/a.txt"}, {"path": "src/new.txt"}],
        }
        fake_paths = types.ModuleType("ForgePYPaths")
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "project"; root.mkdir()
            data = base / "data"; data.mkdir()
            (root / "src").mkdir()
            (root / "src" / "a.txt").write_text("old", encoding="utf-8")
            patch = base / "x.patch"; patch.write_text("x", encoding="utf-8")
            fake_paths.data_root = lambda: data
            with mock.patch.dict(sys.modules, {"ForgePYPatchEngine": fake_engine, "ForgePYPaths": fake_paths}):
                info = checkpoint.create(root, [patch], project_id="demo")
                (root / "src" / "a.txt").write_text("new", encoding="utf-8")
                (root / "src" / "new.txt").write_text("created", encoding="utf-8")
                restored = checkpoint.restore(Path(info["path"]))
            self.assertTrue(restored["ok"])
            self.assertEqual((root / "src" / "a.txt").read_text(encoding="utf-8"), "old")
            self.assertFalse((root / "src" / "new.txt").exists())

    def test_root_forge_command_routes_cli_without_changing_default_gui(self) -> None:
        text = (ROOT / "Forge.cmd").read_text(encoding="utf-8")
        self.assertIn("ForgeUnifiedCli.py", text)
        self.assertIn("performance", text)
        self.assertIn(":GUI", text)
        cli = (APP / "ForgeUnifiedCli.py").read_text(encoding="utf-8")
        self.assertIn("_normalize_global_options", cli)

    def test_executable_plan_is_onedir_bootstrap_not_onefile(self) -> None:
        text = (APP / "ForgeStandaloneBuild.py").read_text(encoding="utf-8")
        self.assertIn("ForgePYBootstrap.py", text)
        self.assertIn('"--standalone"', text)
        self.assertNotIn('"--onefile"', text)
        self.assertIn("portable-onedir", text)
        update = (APP / "ForgeSelfUpdateRuntime.py").read_text(encoding="utf-8")
        self.assertIn("mixed-version install", update)

    def test_intake_git_probe_uses_configured_git_resolver(self) -> None:
        text = (APP / "ForgePYIntake.py").read_text(encoding="utf-8")
        block = text[text.index("def _git_apply_probe"):text.index("def _row", text.index("def _git_apply_probe"))]
        self.assertIn("git = _git_binary()", block)
        self.assertIn('[git, "-C"', block)
        self.assertNotIn('["git", "-C"', block)

    def test_candidate_high_churn_sources_still_not_overwritten(self) -> None:
        self.assertTrue((APP / "ForgeGui.py").is_file())
        self.assertTrue((APP / "ForgeSimplifiedUX.py").is_file())
        self.assertTrue((APP / "VaultIntake.py").is_file())


if __name__ == "__main__":
    unittest.main()
