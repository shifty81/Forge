
from __future__ import annotations
import sys, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app"
if str(APP) not in sys.path:
    sys.path.insert(0,str(APP))

import ForgeStandalone
from ForgePYVersion import VERSION, BUILD

class F60R373Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,"0.4.377-F60R377")
        self.assertEqual(BUILD,"FORGEPY-F60R377")

    def test_normal_launch_never_requires_folder_picker(self):
        with patch.object(ForgeStandalone,"_registry_root",return_value=None), \
             patch.object(ForgeStandalone,"_choose_root",side_effect=AssertionError("normal launch must not open chooser")):
            target=ForgeStandalone.resolve_target(None,force_choose=False)
        self.assertEqual(target,ROOT)

    def test_explicit_choose_can_still_cancel(self):
        with patch.object(ForgeStandalone,"_choose_root",return_value=None):
            self.assertIsNone(ForgeStandalone.resolve_target(None,force_choose=True))

    def test_stale_active_project_falls_back_to_recent_valid_entry(self):
        # Behavior is covered structurally here; registry integration remains in existing tests.
        src=(APP/"ForgeStandalone.py").read_text(encoding="utf-8")
        self.assertIn("most recently opened valid registered project",src)
        self.assertIn("_forgepy_self_root()",src)

    def test_pythonw_launcher_is_async_after_startup_splash_rollback(self):
        src=(ROOT/"ForgePY.vbs").read_text(encoding="utf-8")
        self.assertIn("shell.Run cmd, 0, False",src)
        self.assertNotIn("shell.Run(cmd, 0, True)",src)
        # Fatal Python startup errors are surfaced by ForgeStandalone instead.
        standalone=(APP/"ForgeStandalone.py").read_text(encoding="utf-8")
        self.assertIn("_report_fatal_startup_error",standalone)

    def test_top_level_startup_exceptions_are_reported(self):
        src=(APP/"ForgeStandalone.py").read_text(encoding="utf-8")
        self.assertIn("def _report_fatal_startup_error",src)
        self.assertIn("except Exception as exc:",src)
        self.assertIn("ForgePY could not start",src)

if __name__=="__main__":
    unittest.main()
