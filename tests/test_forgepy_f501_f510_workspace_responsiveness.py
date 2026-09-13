#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class WorkspaceResponsivenessTests(unittest.TestCase):
    def test_performance_policy(self) -> None:
        from ForgeWorkspacePerformance import policy
        data = policy()
        self.assertFalse(data["file_scan_on_ui_thread"])
        self.assertFalse(data["background_workers_touch_tk"])
        self.assertTrue(data["duplicate_refresh_coalescing"])
        self.assertEqual(data["tree_batch_size"], 0)

    def test_async_scan_is_worker_backed(self) -> None:
        text = (APP / "ForgeWorkspaceSurface.py").read_text(encoding="utf-8")
        self.assertIn("ForgeWorkspaceLazyScan", text)
        self.assertIn("from VaultIde import list_files", text)
        self.assertIn("gui.window.after(25, poll)", text)

    def test_tree_population_is_incremental(self) -> None:
        text = (APP / "ForgeWorkspaceSurface.py").read_text(encoding="utf-8")
        self.assertIn("<<TreeviewOpen>>", text)
        self.assertIn("_populate_level", text)

    def test_duplicate_refresh_is_coalesced(self) -> None:
        text = (APP / "ForgeWorkspaceSurface.py").read_text(encoding="utf-8")
        self.assertIn("_forge_workspace_scan_running", text)
        self.assertIn("_forge_workspace_scan_root", text)
        self.assertIn("Scanning project files…", text)

    def test_registered_audit_worker_does_not_log_from_worker(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        start = text.index("def _audit_registered_projects_async")
        end = text.index("def _walk_widgets", start)
        block = text[start:end]
        worker_start = block.index("def worker()")
        poll_start = block.index("def poll(", worker_start)
        worker = block[worker_start:poll_start]
        self.assertNotIn("_safe_log(", worker)
        self.assertIn("_safe_log(", block[poll_start:])


if __name__ == "__main__":
    unittest.main()
