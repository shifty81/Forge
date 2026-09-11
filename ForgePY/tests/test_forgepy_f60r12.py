from pathlib import Path
import json, sys, unittest
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION, BUILD, PRODUCT

class ForgePYF60R12Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION, '0.4.22-F60R22')
        self.assertEqual(BUILD, 'FORGEPY-F60R22')
        self.assertEqual(PRODUCT, 'ForgePY')
    def test_canonical_root(self):
        for name in ('ForgePY.vbs','ForgePY.cmd','ForgePYConsole.cmd','VerifyForgePY.cmd','FORGEPY_PACKAGE_MANIFEST.json'):
            self.assertTrue((ROOT/name).is_file(), name)
        for name in ('ProjectControlCenter.cmd','ProjectControlCenter.vbs','Vault.cmd','Vault.vbs','VaultConsole.cmd','VerifyVault.cmd'):
            self.assertFalse((ROOT/name).exists(), name)
    def test_contract(self):
        d=json.loads((ROOT/'project.control.json').read_text(encoding='utf-8'))
        self.assertEqual(d['project']['id'],'forgepy')
        self.assertEqual(d['project']['name'],'ForgePY')
        self.assertEqual(d['root_control_center']['launcher'],'ForgePY.cmd')
    def test_legacy_shortcut_aliases_remain(self):
        self.assertTrue((ROOT/'Forge.cmd').is_file())
        self.assertTrue((ROOT/'Forge.vbs').is_file())
    def test_legacy_material_moved(self):
        self.assertTrue((ROOT/'compat'/'legacy-launchers'/'ProjectControlCenter.cmd').is_file())
        self.assertTrue((ROOT/'docs'/'history'/'README_STANDALONE.md').is_file())
        self.assertTrue((ROOT/'archive'/'releases'/'Forge_0.4.11-F60R11_UpdateKit.zip').is_file())

if __name__=='__main__': unittest.main()
