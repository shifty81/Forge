#!/usr/bin/env python3
from __future__ import annotations
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class CohesionFinalTests(unittest.TestCase):
    def test_primary_ui_and_embedded_console(self):
        from ForgeUiWorkflowModel import PRIMARY_SURFACES, PROJECT_CLI_MODE
        self.assertEqual([x.label for x in PRIMARY_SURFACES], ["Vault", "Project", "Workspace", "Settings"])
        self.assertEqual(PROJECT_CLI_MODE, "external-project-cli")

    def test_nested_mirror_is_never_governed(self):
        from ForgePackagePolicy import is_governed, classification
        self.assertTrue(is_governed("app/ForgeGui.py"))
        self.assertFalse(is_governed("ForgePY/app/ForgeGui.py"))
        self.assertEqual(classification("ForgePY/app/ForgeGui.py"), "legacy-mirror")

    def test_green_uses_same_governed_policy(self):
        text = (APP / "ForgeGreen.py").read_text(encoding="utf-8")
        self.assertIn("from ForgePackagePolicy import is_governed", text)
        self.assertIn("if not is_governed(rel):", text)
        self.assertNotIn("path.read_bytes()", text)

    def test_manifest_prunes_before_descent(self):
        text = (ROOT / "tools/BuildForgePYManifest.py").read_text(encoding="utf-8")
        self.assertIn("os.walk(ROOT)", text)
        self.assertNotIn("ROOT.rglob", text)
        self.assertIn("not is_governed(rel)", text)

    def test_no_protocol_alias_conflicts(self):
        from ForgeProjectProtocol import protocol_conflicts
        self.assertEqual(protocol_conflicts(), {})

    def test_project_cli_is_distinct_from_forge_console(self):
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn('right_button("PROJECT CLI", self._open_cli)', text)
        self.assertNotIn('button("PROJECT CONSOLE"', text)

    def test_project_tool_rail_is_not_primary_navigation(self):
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn("_forge_project_tool_host", text)
        self.assertIn("host.pack_forget()", text)

    def test_runtime_cortex_execution_delegates(self):
        runtime = (APP / "ForgeRuntimeServices.py").read_text(encoding="utf-8")
        bridge = (APP / "ForgeCortexBridge.py").read_text(encoding="utf-8")
        self.assertIn("def run_canonical(", runtime)
        self.assertIn("from ForgeUnifiedServices import operations", runtime)
        self.assertIn("runtime.run_canonical", bridge)

    def test_load_coordinator_prioritizes_active_interaction(self):
        text = (APP / "ForgeLoadCoordinator.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("while self._interactive_depth > 0"), 2)

    def test_normalization_audit_passes_overlay(self):
        from ForgeNormalizationAudit import audit
        result = audit(ROOT)
        self.assertTrue(result["ok"], result["failed"])

    def test_patch_apply_remains_explicit_only(self):
        text = (APP / "PCCOperationHost.py").read_text(encoding="utf-8")
        self.assertRegex(text, r"AUTO_PATCH_OPERATIONS\s*:\s*set\[str\]\s*=\s*set\(\)")


if __name__ == "__main__":
    unittest.main()
