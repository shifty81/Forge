from __future__ import annotations
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION, BUILD
class F60R390Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,'0.4.415-F60R415'); self.assertEqual(BUILD,'FORGEPY-F60R415')
    def test_no_forgegui_toplevel_windows_remain(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertNotIn('Toplevel(',src)
        self.assertNotIn('wait_window(',src)
    def test_native_file_dialogs_are_owned_by_main_window(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        for marker in ('Choose ForgePY Home','Choose Default Projects Root','Select Forgejo Binary','Register Project Root','Select Blender Python Script','Apply Patch — resolve registered project automatically'):
            pos=src.index(marker); start=max(0,src.rfind('self.filedialog.',0,pos)); call=src[start:pos+len(marker)+160]
            self.assertIn('parent=self.window',call,marker)
    def test_large_internal_surfaces_use_embedded_action_shell(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        for fn in ('_vault_show_lineage_groups','_open_artifact_central_browser','_open_patch_review','_choose_available_download'):
            start=src.index('def '+fn); end=src.find('\n    def ',start+5); block=src[start:end if end>0 else len(src)]
            self.assertIn('_embedded_action_shell',block,fn)
if __name__=='__main__': unittest.main()
