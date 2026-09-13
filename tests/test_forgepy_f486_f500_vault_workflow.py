#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class VaultWorkflowTests(unittest.TestCase):
    def test_vault_workflow_contract(self) -> None:
        from ForgeVaultWorkflow import workflow
        data = workflow()
        self.assertEqual(data["startupSurface"], "vault.projects")
        self.assertEqual(data["steps"][0]["key"], "project.add")
        self.assertIn("vault.library", {x["key"] for x in data["advanced"]})

    def test_left_rail_is_normalized(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn('"Operations", "Updates", "Projects", "Source Control", "Cortex"', text)
        self.assertIn('for key in ("Vault", "Project Workspace", "IDE", "Settings")', text)

    def test_vault_lands_on_projects_not_catalog(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn('if name in {"Projects", "Vault"}:', text)
        self.assertIn('_show_vault_projects(self, original_show_app)', text)
        self.assertIn('gui._forge_vault_view = "Projects"', text)

    def test_library_is_secondary(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn('button("LIBRARY"', text)
        self.assertIn('_show_vault_library', text)
        self.assertIn('button("PROJECTS"', text)

    def test_patch_picker_not_duplicated_in_vault_quickbar(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        render = text[text.index("def render_quickbar"):text.index("def build_quick_actions")]
        vault_branch = render[render.index('if tab == "Vault"'):render.index('elif tab == "Project Workspace"')]
        self.assertNotIn('SELECT PATCH', vault_branch)

    def test_open_project_routes_to_dashboard(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn('_open_selected_project_dashboard', text)
        self.assertIn('gui._show_page("Dashboard")', text)
        self.assertIn('original_show_app(gui, "Project Workspace")', text)


if __name__ == "__main__":
    unittest.main()
