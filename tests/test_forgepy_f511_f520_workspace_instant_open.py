#!/usr/bin/env python3
from __future__ import annotations
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

class WorkspaceInstantOpenTests(unittest.TestCase):
    def test_policy(self) -> None:
        from ForgeWorkspacePerformance import policy
        p = policy()
        self.assertFalse(p["external_runtime_probe_on_open"])
        self.assertFalse(p["monaco_pywebview_required"])
        self.assertFalse(p["full_tree_population_on_open"])
        self.assertTrue(p["lazy_directory_materialization"])
        self.assertTrue(p["workspace_shell_prebuilt"])
        self.assertTrue(p["cached_index_reused_on_tab_return"])

    def test_builder_has_no_external_probe(self) -> None:
        text = (APP / "ForgeWorkspaceSurface.py").read_text(encoding="utf-8")
        build = text[text.index("def build("):]
        self.assertNotIn("runtime_ready", build)
        self.assertNotIn("host_ready", build)
        self.assertNotIn("pywebview", build)
        self.assertNotIn("Monaco", build)

    def test_lazy_scan_and_tree(self) -> None:
        text = (APP / "ForgeWorkspaceSurface.py").read_text(encoding="utf-8")
        self.assertIn("ForgeWorkspaceLazyScan", text)
        self.assertIn("<<TreeviewOpen>>", text)
        self.assertIn("_populate_level", text)
        self.assertIn("_forge_workspace_index_root", text)

    def test_prebuild_does_not_scan(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        start = text.index("def _prebuild_workspace_shell")
        end = text.index("def patch_simplified_ux", start)
        block = text[start:end]
        self.assertIn('builder(frame)', block)
        self.assertNotIn('refresh_files', block)
        self.assertRegex(text, r'self\.window\.after\((?:300|350), lambda: _prebuild_workspace_shell\(self\)\)')

    def test_builder_is_replaced(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn("cls._build_ide_tab = workspace_build", text)
        self.assertIn("cls._ide_refresh_files = workspace_refresh", text)

if __name__ == "__main__":
    unittest.main()
