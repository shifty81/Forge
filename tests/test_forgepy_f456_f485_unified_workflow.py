#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class ForgePYUnifiedWorkflowTests(unittest.TestCase):
    def test_protocol_aliases_are_canonical(self) -> None:
        from ForgeProjectProtocol import normalize_key
        self.assertEqual(normalize_key("full"), "gate.full")
        self.assertEqual(normalize_key("build.native"), "build.default")
        self.assertEqual(normalize_key("patch-apply"), "patch.apply-staged")

    def test_protocol_grade(self) -> None:
        from ForgeProjectProtocol import integration_grade
        grade = integration_grade(["gate.full", "build.default"])
        self.assertIn(grade["grade"], {"AUDITING", "ADAPTED", "STANDARDIZED"})
        self.assertNotIn("patch.queue", grade["standardMissing"])
        self.assertIn("patch.queue", grade["forgePyCapabilities"])

    def test_command_bus_alias_and_metadata(self) -> None:
        from ForgeCommandBus import CommandBus
        bus = CommandBus()
        bus.register("build.default", lambda: 7, aliases=("build",), label="Build", category="Build & Test")
        result = bus.execute("build")
        self.assertTrue(result.ok)
        self.assertEqual(result.value, 7)
        self.assertEqual(result.canonical_key, "build.default")
        self.assertEqual(bus.describe()[0]["label"], "Build")

    def test_operation_envelope(self) -> None:
        from ForgeOperationEnvelope import OperationTranscript
        tx = OperationTranscript("demo", "build.default", initiator="test")
        tx.emit("output", "hello")
        done = tx.finish(ok=True, result={"x": 1})
        self.assertTrue(done["ok"])
        self.assertEqual(done["events"][0]["event_type"], "output")

    def test_operation_host_has_no_implicit_patch_consumption(self) -> None:
        text = (APP / "PCCOperationHost.py").read_text(encoding="utf-8")
        self.assertIn("AUTO_PATCH_OPERATIONS: set[str] = set()", text)
        self.assertIn('if operation == "patch-apply":', text)
        self.assertNotIn('operation in PATCH_APPLY_OPERATIONS', text)

    def test_queue_only_workflow_is_installed_without_replacing_gui(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn("Nothing was applied", text)
        self.assertIn('if name in {"Projects", "Vault"}:', text)
        self.assertIn('"Queue Patch"', text)
        self.assertIn('"PROJECT CLI"', text)
        self.assertIn("_focus_console", text)
        self.assertTrue((APP / "ForgeGui.py").is_file(), "integrated repository must retain canonical ForgeGui.py")

    def test_project_audit_writes_two_handoffs(self) -> None:
        text = (APP / "ForgeProjectAudit.py").read_text(encoding="utf-8")
        self.assertIn("FORGEPY_SUPPORT_HANDOFF.md", text)
        self.assertIn("PROJECT_INTEGRATION_HANDOFF.md", text)
        self.assertIn("PROJECT_INTELLIGENCE.json", text)

    def test_cli_exposes_queue_and_handoffs(self) -> None:
        text = (APP / "ForgeUnifiedCli.py").read_text(encoding="utf-8")
        self.assertIn('patch_sub.add_parser("queue")', text)
        self.assertIn('project_sub.add_parser("handoffs")', text)
        self.assertIn("--stream-json", text)


    def test_scanned_registration_triggers_handoffs(self) -> None:
        text = (APP / "ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        self.assertIn("_audit_registered_projects_async", text)
        self.assertIn("write_handoffs(root, deep=False)", text)
        self.assertIn("cls._vault_register_scanned_projects = register_scanned_projects", text)


if __name__ == "__main__":
    unittest.main()
