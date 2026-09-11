from __future__ import annotations
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/'app'
if str(APP) not in sys.path:sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION,BUILD
class F60R375Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,'0.4.379-F60R379'); self.assertEqual(BUILD,'FORGEPY-F60R379')
    def test_preimport_bootstrap_exists(self):
        src=(APP/'ForgePYBootstrap.py').read_text(encoding='utf-8')
        self.assertLess(src.index('initialize()'),src.index('import ForgeStandalone'))
        self.assertIn('forgepy-bootstrap-latest.log',(APP/'ForgeBootstrapLog.py').read_text(encoding='utf-8'))
    def test_launchers_use_bootstrap(self):
        for name in ('ForgePY.vbs','ForgePY.cmd','ForgePYConsole.cmd','VerifyForgePY.cmd'):
            self.assertIn('ForgePYBootstrap.py',(ROOT/name).read_text(encoding='utf-8'))
    def test_standalone_does_not_import_gui_at_module_import_time(self):
        src=(APP/'ForgeStandalone.py').read_text(encoding='utf-8')
        pre=src[:src.index('def main(')]
        self.assertNotIn('from ForgeGui import',pre)
        self.assertIn('IMPORT_FORGE_GUI_START',src)
    def test_gui_has_phase_markers(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        for marker in ('GUI_TK_ROOT_CREATE_START','GUI_TK_ROOT_CREATE_PASS','GUI_SHELL_BUILD_PASS','GUI_INIT_COMPLETE','GUI_MAINLOOP_START'):
            self.assertIn(marker,src)
    def test_watchers_are_deferred_until_after_mainloop_begins(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('self.window.after(700, self._start_intake_watcher)',src)
        self.assertNotIn('\n        self._start_intake_watcher()\n',src[src.index('class ForgeGui'):src.index('    # ------------------------------------------------------------------\n    # Shell / styling')])
    def test_debug_launcher_always_pauses(self):
        src=(ROOT/'ForgePYDebug.cmd').read_text(encoding='utf-8')
        self.assertIn('pause',src.casefold()); self.assertIn('forgepy-bootstrap-latest.log',src)
if __name__=='__main__':unittest.main()
