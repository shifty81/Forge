from __future__ import annotations
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION, BUILD

class ForgePYF60R65Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,'0.4.390-F60R390'); self.assertEqual(BUILD,'FORGEPY-F60R390')
    def test_single_tk_root_contract(self):
        # F60R374 supersedes the temporary shared-splash-root approach: normal
        # startup now creates only the main ForgeGui Tk root.
        standalone=(APP/'ForgeStandalone.py').read_text(encoding='utf-8')
        gui=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertNotIn('show_startup_screen',standalone)
        self.assertNotIn('keep_root=True',standalone)
        self.assertIn('return ForgeGui(target).run()',standalone)
        self.assertIn('window if window is not None else tk.Tk()',gui)
    def test_native_services_are_staged_after_first_paint(self):
        gui=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('self.window.after(2500, self._start_tray)',gui)
        self.assertIn('self.window.after(5000, self._start_background_census)',gui)
    def test_native_crash_diagnostics_are_enabled(self):
        standalone=(APP/'ForgeStandalone.py').read_text(encoding='utf-8')
        self.assertIn('faulthandler.enable',standalone)
        self.assertIn('Logs" / "crashes',standalone)
    def test_tray_has_explicit_pointer_sized_api_prototypes(self):
        tray=(APP/'VaultTray.py').read_text(encoding='utf-8')
        self.assertIn('AppendMenuW.argtypes',tray)
        self.assertIn('GetMessageW.argtypes',tray)
        self.assertIn('DispatchMessageW.argtypes',tray)

if __name__=='__main__': unittest.main()
