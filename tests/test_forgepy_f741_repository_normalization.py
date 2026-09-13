from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ForgePYF741RepositoryNormalizationTests(unittest.TestCase):
    def test_one_canonical_source_tree(self) -> None:
        self.assertTrue((ROOT / "app" / "ForgePYBootstrap.py").is_file())
        self.assertFalse((ROOT / "ForgePY").exists(), "nested ForgePY source mirror must not return")

    def test_operational_root_has_no_repair_payloads(self) -> None:
        forbidden = {
            "README_FIRST.txt",
            "REPAIR_MANIFEST.json",
            "RUN_REPAIR.cmd",
            "OVERWRITE_SOURCE_MANIFEST.json",
            "OVERWRITE_SOURCE_README.txt",
            "PublishForgePYRepository.cmd",
            "PublishForgePYRepository.ps1",
            "overwrite_source",
        }
        present = {p.name for p in ROOT.iterdir()}
        self.assertFalse(forbidden & present, sorted(forbidden & present))

    def test_documentation_has_current_structure(self) -> None:
        for rel in (
            "docs/README.md",
            "docs/current/SOURCE_AUDIT_20260912.md",
            "docs/architecture/ARCHITECTURE.md",
            "docs/guides/PROJECT_ONBOARDING.md",
            "docs/integrations/TOOL_ACTIVATION_CONTRACT.md",
            "docs/history/certification/F450_F740_CERTIFICATION.json",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_console_has_one_stop_beside_send_and_last_run_is_statusbar_state(self) -> None:
        active = (ROOT / "app" / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertNotIn('"Stop Active Job"', active)
        self.assertIn('gui.stop_btn = gui._button(row, "Stop"', active)
        self.assertIn('gui._button(row, "Send", gui._console_execute_entry', active)
        self.assertIn('gui._forge_status_last_run', active)
        console_block = active[active.index("def _console("):active.index("def _refresh_console_catalog")]
        self.assertEqual(console_block.count('gui._button(row, "Stop"'), 1)

    def test_explicit_source_normalizer_exists_for_legacy_checkouts(self) -> None:
        tool = ROOT / "tools" / "repository" / "NormalizeForgePYSource.py"
        self.assertTrue(tool.is_file())
        text = tool.read_text(encoding="utf-8")
        self.assertIn('"ForgePY"', text)
        self.assertIn('if not before["canonicalOk"]', text)

    def test_status_render_and_cancel_paths_are_layout_safe(self) -> None:
        gui = (ROOT / "app" / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn('widget = getattr(self, "summary_text", None)', gui)
        self.assertIn('self._operation_cancel.set()', gui)
        self.assertIn('terminate_process_tree', gui)
        self.assertIn('"universal-project-apply-cancelled"', gui)
        self.assertNotIn('self.console_job_label =', gui)


if __name__ == "__main__":
    unittest.main()
