#!/usr/bin/env python3
from __future__ import annotations
import sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/"app"
if str(APP) not in sys.path: sys.path.insert(0,str(APP))

class F700Tests(unittest.TestCase):
    def test_runtime_patches_visible_gui_identity(self):
        text=(APP/"ForgeRuntimeCompatibility.py").read_text(encoding="utf-8")
        self.assertIn('setattr(gui_module, "FORGE_VERSION", DISPLAY_VERSION)',text)
        self.assertIn('setattr(gui_module, "GUI_VERSION"',text)
        self.assertIn('setattr(standalone_module, "FORGE_VERSION", DISPLAY_VERSION)',text)

    def test_candidate_identity(self):
        from ForgeApplicationIdentity import DISPLAY_VERSION,DISPLAY_BUILD,CANDIDATE_REVISION
        self.assertEqual(DISPLAY_VERSION,"0.5.0-candidate.777")
        self.assertEqual(DISPLAY_BUILD,"FORGEPY-F777")
        self.assertEqual(CANDIDATE_REVISION,777)

    def test_project_identity_is_bounded(self):
        from ForgeProjectIdentity import resolve
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"project.control.json").write_text('{"project":{"id":"x","name":"X","version":"1.2.3","build":"X-42"}}',encoding="utf-8")
            row=resolve(root)
        self.assertEqual(row["projectVersion"],"1.2.3")
        self.assertEqual(row["projectBuild"],"X-42")

    def test_dashboard_is_functional(self):
        text=(APP/"ForgeProjectDashboard.py").read_text(encoding="utf-8")
        for token in ("UPDATES","SOURCE & RECOVERY","DIAGNOSTICS","PROJECT TOOLS","ADVANCED","Needs Attention"):
            self.assertIn(token,text)

    def test_workspace_quick_open(self):
        text=(APP/"ForgeWorkspaceSurface.py").read_text(encoding="utf-8")
        self.assertIn("QUICK OPEN",text)
        self.assertIn("def quick_filter",text)
        self.assertIn("_workspace_overview",text)

    def test_install_modes(self):
        from ForgeInstallerRuntime import choices
        self.assertEqual({x["mode"] for x in choices()},{"installed","portable"})

    def test_self_maintenance_ui_is_worker_backed(self):
        text=(APP/"ForgeSelfMaintenanceUI.py").read_text(encoding="utf-8")
        self.assertIn("def run_background",text)
        self.assertIn("threading.Thread",text)
        self.assertIn("ForgeSelfMaintenance-",text)

    def test_self_update_is_directory_transaction(self):
        text=(APP/"ForgeSelfMaintenance.py").read_text(encoding="utf-8")
        self.assertIn("queue_update",text)
        self.assertIn("prepare_patch",text)
        self.assertIn("promotion_powershell",text)
        self.assertIn("apply_transport(transport, staged)",text)
        self.assertIn(".forgeupdate",text)

    def test_no_duplicate_activation_handoff_thread(self):
        text=(APP/"ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertNotIn('name="ForgeProjectAuditHandoff"',text)

    def test_project_specialist_pages_are_lazy(self):
        text=(APP/"ForgeProjectSurface.py").read_text(encoding="utf-8")
        self.assertIn("def ensure_page",text)
        self.assertIn("_forge_project_pages_built",text)
        self.assertIn('ensure_page(gui,"Dashboard")',text)

    def test_application_layout_does_not_use_selected_project_cwd(self):
        text=(APP/"ForgeInstallLayout.py").read_text(encoding="utf-8")
        self.assertIn("def application_root",text)
        self.assertIn('executable.name.casefold() == "forgepy.exe"',text)
        self.assertNotIn("app_root or Path.cwd()",text)

    def test_runtime_creates_application_state_after_first_paint(self):
        text=(APP/"ForgePerformanceRuntime.py").read_text(encoding="utf-8")
        self.assertIn("ensure_application_layout",text)
        self.assertIn("self.window.after(250, ensure_application_layout)",text)

    def test_old_sync_project_open_is_not_rebound(self):
        text=(APP/"ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertNotIn("cls._open_selected_project = lambda self: _open_selected_project_dashboard",text)

    def test_surface_once_normalization(self):
        text=(APP/"ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn("def _normalize_surface_once",text)
        show=text[text.index("def show_app"):text.index("def activate_project")]
        self.assertNotIn("_normalize_user_facing_terms(self)",show)

if __name__=="__main__":
    unittest.main()
