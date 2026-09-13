#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class PerformanceReliabilityTests(unittest.TestCase):
    def test_fast_source_status_uses_porcelain_v2_and_two_git_calls(self) -> None:
        import ForgeStatusCache as cache
        calls: list[list[str]] = []

        def fake_run(root: Path, args: list[str], timeout: float = 15.0):
            calls.append(list(args))
            if args[0] == "status":
                output = (
                    "# branch.oid abcdef1234567890\n"
                    "# branch.head main\n"
                    "# branch.upstream origin/main\n"
                    "# branch.ab +0 -0\n"
                )
            else:
                output = (
                    "origin https://github.com/test/repo.git (fetch)\n"
                    "origin https://github.com/test/repo.git (push)\n"
                )
            return subprocess.CompletedProcess([], 0, stdout=output)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            cache.clear(root)
            with mock.patch.object(cache.shutil, "which", return_value="git"), \
                 mock.patch.object(cache, "_run_git", side_effect=fake_run), \
                 mock.patch.object(cache, "_declared_github", return_value={"cloneUrl": "", "webUrl": "", "remote": ""}):
                data = cache.fast_source_status(root, force=True)
        self.assertEqual(len(calls), 2)
        self.assertIn("--porcelain=v2", calls[0])
        self.assertEqual(data["branch"], "main")
        self.assertTrue(data["clean"])

    def test_selection_is_debounced_and_backgrounded(self) -> None:
        text = (APP / "ForgeProjectInteractionPerformance.py").read_text(encoding="utf-8")
        start = text.index("def project_selection_changed")
        end = text.index("def activate_project", start)
        block = text[start:end]
        self.assertIn("self.window.after(120, begin)", block)
        self.assertIn('name="ForgeProjectPreview"', block)
        before_worker = block[:block.index("def worker()")]
        self.assertNotIn("ProjectContract.load(", before_worker)
        self.assertIn("_forge_preview_results", block)

    def test_activation_is_async_and_hygiene_deferred(self) -> None:
        text = (APP / "ForgeProjectInteractionPerformance.py").read_text(encoding="utf-8")
        start = text.index("def activate_project")
        end = text.index("def open_selected_project", start)
        block = text[start:end]
        self.assertIn('name="ForgeProjectActivate"', block)
        self.assertIn("ProjectContract.load(target)", block)
        self.assertNotIn("repo_hygiene_prepare", block)
        self.assertIn("self.window.after(900, lambda: _background_hygiene", block)
        self.assertNotIn("clear_status_cache(target)", block)

    def test_quickbar_open_uses_final_async_open(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn('button("OPEN PROJECT", self._open_selected_project)', text)
        self.assertIn("install_project_interaction(cls)", text)
        self.assertIn("install_performance_runtime(cls)", text)

    def test_status_patch_installed_by_compat_layer(self) -> None:
        text = (APP / "ForgeRuntimeCompatibility.py").read_text(encoding="utf-8")
        self.assertIn("patch_runtime_modules", text)
        self.assertIn("patch_fast_status(module)", text)
        self.assertIn("FORGEPY-RUNTIME-COMPAT-F700", text)

    def test_census_is_deferred_and_ui_lag_is_measured(self) -> None:
        text = (APP / "ForgePerformanceRuntime.py").read_text(encoding="utf-8")
        self.assertIn("25000", text)
        self.assertIn("COORDINATOR.interactive_recent(8.0)", text)
        self.assertIn("ui-event-loop-lag", text)

    def test_jobs_are_bounded_atomic_and_release_futures(self) -> None:
        text = (APP / "ForgeJobs.py").read_text(encoding="utf-8")
        self.assertIn("_MAX_HISTORY = 500", text)
        self.assertIn("self._persist_lock", text)
        self.assertIn("os.replace(temp, path)", text)
        self.assertIn("self._futures.pop(job.job_id, None)", text)

    def test_load_coordinator_serializes_scan_lane(self) -> None:
        from ForgeLoadCoordinator import LoadCoordinator
        coordinator = LoadCoordinator()
        active = 0
        maximum = 0
        guard = threading.Lock()

        def work() -> None:
            nonlocal active, maximum
            with coordinator.scan("test", wait_for_idle=0):
                with guard:
                    active += 1
                    maximum = max(maximum, active)
                time.sleep(0.02)
                with guard:
                    active -= 1

        a = threading.Thread(target=work)
        b = threading.Thread(target=work)
        a.start(); b.start(); a.join(); b.join()
        self.assertEqual(maximum, 1)

    def test_static_audit_detects_recursive_scan_and_duplicate_authority(self) -> None:
        from ForgePerformanceAudit import audit
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app = root / "app"
            mirror = root / "ForgePY" / "app"
            app.mkdir(parents=True)
            mirror.mkdir(parents=True)
            code = (
                "import os, subprocess\n"
                "def f(root):\n"
                "    for base, dirs, files in os.walk(root):\n"
                "        subprocess.run(['x'])\n"
            )
            (app / "A.py").write_text(code, encoding="utf-8")
            (mirror / "A.py").write_text(code, encoding="utf-8")
            report = audit(root)
        kinds = {item["kind"] for item in report["findings"]}
        self.assertIn("recursive-scan", kinds)
        self.assertIn("subprocess", kinds)
        self.assertIn("duplicate-source-authority", kinds)

    def test_candidate_gui_sources_are_not_replaced(self) -> None:
        self.assertTrue((APP / "ForgeGui.py").is_file())
        self.assertTrue((APP / "ForgeSimplifiedUX.py").is_file())
        self.assertTrue((APP / "VaultIntake.py").is_file())


if __name__ == "__main__":
    unittest.main()
