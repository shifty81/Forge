from __future__ import annotations
import sys, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
import ForgeStandalone
from ForgePYVersion import VERSION,BUILD

class F60R374Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,'0.4.415-F60R415')
        self.assertEqual(BUILD,'FORGEPY-F60R415')

    def test_normal_main_does_not_call_startup_splash(self):
        src=(APP/'ForgeStandalone.py').read_text(encoding='utf-8')
        self.assertNotIn('show_startup_screen',src)
        self.assertNotIn('load_startup_settings',src)
        self.assertIn('return ForgeGui(target).run()',src)

    def test_normal_main_bootstraps_without_tk_before_gui(self):
        order=[]
        class FakeGui:
            def __init__(self,target): order.append(('gui',target))
            def run(self): order.append(('run',None)); return 0
        with patch.object(ForgeStandalone,'resolve_target',return_value=ROOT),              patch.object(ForgeStandalone,'ensure_forgepy_layout',side_effect=lambda: order.append(('layout',None))),              patch.object(ForgeStandalone,'forgepy_first_run_needed',return_value=False),              patch.object(ForgeStandalone,'ForgeGui',FakeGui):
            rc=ForgeStandalone.main([])
        self.assertEqual(rc,0)
        self.assertEqual(order[0][0],'layout')
        self.assertEqual(order[1][0],'gui')
        self.assertEqual(order[2][0],'run')

    def test_vbs_launcher_is_async_and_has_no_startup_window_wait(self):
        src=(ROOT/'ForgePY.vbs').read_text(encoding='utf-8')
        self.assertIn('shell.Run cmd, 0, False',src)
        self.assertNotIn('shell.Run(cmd, 0, True)',src)

    def test_legacy_splash_setting_defaults_off(self):
        src=(APP/'VaultSettings.py').read_text(encoding='utf-8')
        self.assertIn('"startupSelfTest": False',src)

if __name__=='__main__': unittest.main()
