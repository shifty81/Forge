from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))

class ForgeF60R7Tests(unittest.TestCase):
    def test_version_authority(self):
        from ForgeVersion import VERSION, BUILD
        self.assertEqual(VERSION, "0.4.389-F60R389")
        self.assertEqual(BUILD, "FORGEPY-F60R389")

    def test_green_git_probes_are_no_window_and_cached(self):
        text=(APP/'ForgeGreen.py').read_text(encoding='utf-8')
        self.assertIn('CREATE_NO_WINDOW', text)
        self.assertIn('_GREEN_CACHE', text)
        self.assertIn('_green_cache_token', text)

    def test_gui_background_cadence_and_overlap_guards(self):
        text=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('_status_refresh_running', text)
        self.assertIn('healthRefreshSeconds", 30', text)
        self.assertIn('visible and not self._busy and not self._active_health_scan_running', text)
        self.assertIn('processed < 160', text)
        self.assertIn('0.014', text)

    def test_project_refresh_is_cache_first_and_rescan_explicit(self):
        text=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('def _refresh_projects(self, *, full_rescan: bool = False, refresh_health: bool = False)', text)
        self.assertIn('if full_rescan:', text)
        self.assertIn('if refresh_health:', text)
        self.assertIn('full_rescan=True, refresh_health=True', text)

    def test_restart_no_longer_executes_vbs(self):
        text=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        method=text.split('def _offer_restart_if_updated',1)[1].split('def _latest_applied_patch_identity',1)[0]
        self.assertNotIn('Forge.vbs', method)
        self.assertNotIn('os.startfile', method)
        self.assertIn('pythonw.exe', method)

    def test_owned_text_prompts_replace_simpledialog_in_workflows(self):
        text=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('def _ask_text', text)
        self.assertIn('dialog.transient(self.window)', text)
        self.assertIn('dialog.grab_set()', text)
        self.assertNotIn('self.simpledialog.askstring', text)

if __name__=='__main__': unittest.main()
