#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class ConsoleLayoutTests(unittest.TestCase):
    def test_console_is_forge_console(self) -> None:
        from ForgeUiWorkflowModel import USER_FACING_RENAMES, CONSOLE_LABEL
        self.assertEqual(CONSOLE_LABEL, "FORGE CONSOLE")
        self.assertEqual(USER_FACING_RENAMES["PROJECT CONSOLE"], "FORGE CONSOLE")

    def test_project_cli_is_external_and_far_right(self) -> None:
        from ForgeUiWorkflowModel import PROJECT_CLI_MODE
        self.assertEqual(PROJECT_CLI_MODE, "external-project-cli")
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn('right_button("PROJECT CLI", self._open_cli)', text)
        project = text[text.index('elif tab == "Project Workspace"'):text.index('elif tab == "IDE"')]
        self.assertLess(project.index('right_button("PROJECT CLI"'), project.index('button("FULL GATE"'))

    def test_layout_policy_has_shared_insets(self) -> None:
        from ForgeLayoutNormalization import (
            SURFACE_INSET_X, SURFACE_INSET_Y,
            CONSOLE_INSET_X, CONSOLE_TOP_Y,
            PROJECT_CENTER_INSET_X, PROJECT_CENTER_INSET_Y,
        )
        self.assertEqual((SURFACE_INSET_X, SURFACE_INSET_Y), (8, 6))
        self.assertEqual((CONSOLE_INSET_X, CONSOLE_TOP_Y), (8, 6))
        self.assertEqual((PROJECT_CENTER_INSET_X, PROJECT_CENTER_INSET_Y), (8, 6))

    def test_project_double_padding_is_removed(self) -> None:
        text = (APP / "ForgeLayoutNormalization.py").read_text(encoding="utf-8")
        self.assertIn('padx=0, pady=0', text)
        self.assertIn('content,', text)
        self.assertIn('padx=PROJECT_CENTER_INSET_X', text)

    def test_alignment_reapplies_after_lazy_build_and_resize(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn('schedule_layout(self, 8)', text)
        self.assertIn('self.window.bind("<Configure>"', text)

    def test_native_workspace_uses_same_inset(self) -> None:
        text = (APP / "ForgeWorkspaceSurface.py").read_text(encoding="utf-8")
        self.assertIn("padx=8, pady=6", text)


if __name__ == "__main__":
    unittest.main()
