#!/usr/bin/env python3
from __future__ import annotations
import sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path: sys.path.insert(0, str(APP))

class CohesiveNormalizationTests(unittest.TestCase):
    def test_ui_model_has_exact_primary_workflow(self):
        from ForgeUiWorkflowModel import surface_model
        data = surface_model()
        self.assertEqual([x["label"] for x in data["primary"]], ["Vault", "Project", "Workspace", "Settings"])
        self.assertEqual(data["projectCliMode"], "external-project-cli")
        self.assertEqual(data["ownership"]["patchIntake"], "right-rail")

    def test_project_quickbar_is_contextual_and_cli_is_distinct(self):
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        start = text.index("def render_quickbar")
        end = text.index("def build_quick_actions", start)
        block = text[start:end]
        self.assertIn('project_page == "Updates"', block)
        self.assertIn('project_page == "Source Control"', block)
        self.assertIn('project_page == "Diagnostics"', block)
        self.assertIn('right_button("PROJECT CLI", self._open_cli)', block)
        # Apply Updates must not be a default Dashboard action.
        default = block[block.index('else:\n                    button("FULL GATE"'):block.index('elif tab == "IDE"')]
        self.assertNotIn('APPLY UPDATES', default)

    def test_legacy_monaco_controls_are_hidden(self):
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn("_hide_legacy_workspace_settings", text)
        self.assertIn('"monaco" in text or "pywebview" in text', text)

    def test_forgegit_user_facing_terms_are_canonical(self):
        from ForgeUiWorkflowModel import USER_FACING_RENAMES
        self.assertEqual(USER_FACING_RENAMES["Local Source"], "ForgeGit")
        self.assertEqual(USER_FACING_RENAMES["BACKUP SOURCE"], "SNAPSHOT TO FORGEGIT")

    def test_provider_mapping_is_owned_by_protocol(self):
        from ForgeProjectProtocol import provider_command
        self.assertEqual(provider_command("gate.full"), "full")
        self.assertEqual(provider_command("build.default"), "build")
        service = (APP / "ForgeUnifiedServices.py").read_text(encoding="utf-8")
        self.assertNotIn("COMMAND_TO_PROVIDER", service)
        self.assertIn("provider_command(canonical)", service)

    def test_operation_guard_is_single_flight(self):
        from ForgeOperationGuard import OperationGuard
        g = OperationGuard()
        a = g.acquire("p", "diagnostics.bundle")
        self.assertIsNotNone(a)
        self.assertIsNone(g.acquire("p", "diagnostics.bundle"))
        g.release(a)

    def test_nested_mirror_is_not_governed(self):
        from ForgePackagePolicy import classification, is_governed
        self.assertEqual(classification("ForgePY/app/ForgeGui.py"), "legacy-mirror")
        self.assertFalse(is_governed("ForgePY/app/ForgeGui.py"))
        self.assertTrue(is_governed("app/ForgeGui.py"))

    def test_source_tree_report_detects_divergence(self):
        from ForgeSourceTreePolicy import report
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root/"app").mkdir(); (root/"ForgePY"/"app").mkdir(parents=True)
            (root/"app"/"A.py").write_text("a", encoding="utf-8")
            (root/"ForgePY"/"app"/"A.py").write_text("b", encoding="utf-8")
            data = report(root)
        self.assertEqual(data["divergentCount"], 1)

    def test_gate_has_timeouts_and_source_authority_check(self):
        text = (ROOT / "tools/ForgeGate.py").read_text(encoding="utf-8")
        self.assertIn("source_authority_check", text)
        self.assertIn("timeout=180", text)
        self.assertIn("timeout=1800", text)

    def test_vault_preview_integrates_source_and_updates(self):
        text = (APP / "ForgeProjectInteractionPerformance.py").read_text(encoding="utf-8")
        self.assertIn("ForgeGit   :", text)
        self.assertIn("Updates    :", text)
        self.assertIn("counts_for_project", text)

    def test_right_rail_patch_intake_is_not_hidden(self):
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        normalize = text[text.index("def _normalize_user_facing_terms"):text.index("def _normalize_left_navigation")]
        self.assertNotIn("_forge_patch_drop_button", normalize)

    def test_candidate_high_churn_sources_still_not_replaced(self):
        self.assertTrue((APP / "ForgeGui.py").is_file())
        self.assertTrue((APP / "ForgeSimplifiedUX.py").is_file())
        self.assertTrue((APP / "VaultIntake.py").is_file())

if __name__ == "__main__": unittest.main()
