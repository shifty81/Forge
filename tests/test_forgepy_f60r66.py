from __future__ import annotations
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import VaultTray
from ForgePYVersion import VERSION, BUILD


class ForgePYF60R66Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION, "0.4.389-F60R389")
        self.assertEqual(BUILD, "FORGEPY-F60R389")

    def test_startup_keep_root_quits_hidden_splash_loop(self):
        src = (APP / "ForgeStartup.py").read_text(encoding="utf-8")
        self.assertIn("root.withdraw()", src)
        self.assertIn("root.quit()", src)

    def test_legacy_native_tray_is_fail_closed_on_python314(self):
        with patch.object(VaultTray.os, "name", "nt"), \
             patch.object(VaultTray.sys, "version_info", (3, 14, 0)), \
             patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FORGEPY_ENABLE_LEGACY_NATIVE_TRAY", None)
            os.environ.pop("FORGEPY_DISABLE_TRAY", None)
            self.assertFalse(VaultTray.supported())

    def test_legacy_native_tray_can_be_explicitly_opted_in_for_diagnostics(self):
        with patch.object(VaultTray.os, "name", "nt"), \
             patch.object(VaultTray.sys, "version_info", (3, 14, 0)), \
             patch.dict(os.environ, {"FORGEPY_ENABLE_LEGACY_NATIVE_TRAY": "1"}, clear=False):
            os.environ.pop("FORGEPY_DISABLE_TRAY", None)
            self.assertTrue(VaultTray.supported())

    def test_normal_cmd_is_foreground_diagnostic_after_f408_normalization(self):
        src = (ROOT / "ForgePY.cmd").read_text(encoding="utf-8")
        self.assertIn('python.exe "%FORGEPY_APP%" %*', src)
        self.assertNotIn('start ""', src)
        self.assertNotIn("pythonw.exe", src)
        self.assertTrue((ROOT / "ForgePY.vbs").is_file())


if __name__ == "__main__":
    unittest.main()
