from __future__ import annotations
import subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/'app'
if str(APP) not in sys.path:sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION,BUILD
from ForgeUnifiedDiffPatch import is_unified_diff,validate,apply
from VaultIntake import inspect_patch,looks_like_patch
from ForgePerformance import record

PATCH='''diff --git a/hello.txt b/hello.txt\nindex ce01362..94954ab 100644\n--- a/hello.txt\n+++ b/hello.txt\n@@ -1 +1 @@\n-hello\n+hello forge\n'''
class F60R377Tests(unittest.TestCase):
    def test_identity(self):self.assertEqual((VERSION,BUILD),('0.4.389-F60R389','FORGEPY-F60R389'))
    def _repo(self):
        td=tempfile.TemporaryDirectory(); root=Path(td.name); subprocess.run(['git','init','-q',str(root)],check=True)
        subprocess.run(['git','-C',str(root),'config','user.email','forgepy@test.local'],check=True)
        subprocess.run(['git','-C',str(root),'config','user.name','ForgePY Test'],check=True)
        (root/'hello.txt').write_text('hello\n',encoding='utf-8'); subprocess.run(['git','-C',str(root),'add','hello.txt'],check=True); subprocess.run(['git','-C',str(root),'commit','-qm','base'],check=True)
        p=root/'sample.patch'; p.write_text(PATCH,encoding='utf-8'); return td,root,p
    def test_plain_patch_is_first_class_transport(self):
        td,root,p=self._repo()
        try:
            self.assertTrue(is_unified_diff(p)); self.assertTrue(looks_like_patch(p)); info=inspect_patch(p,project_hint=root)
            self.assertEqual(info['schema'],'forge.patch.unified-diff.v1'); self.assertEqual(info['transportFormat'],'unified-diff')
            self.assertTrue(validate(p,root)['ok'])
        finally:td.cleanup()
    def test_unified_diff_applies_transactionally(self):
        td,root,p=self._repo()
        try:
            receipt=apply(p,root); self.assertEqual(receipt['status'],'applied'); self.assertEqual((root/'hello.txt').read_text(),'hello forge\n')
        finally:td.cleanup()
    def test_manual_picker_copy_no_longer_says_archive_only(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8'); self.assertIn('manifest package or Git unified diff',src)
    def test_confirmation_modals_are_not_demoted(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8'); self.assertNotIn('attributes("-topmost", False)',src)
if __name__=='__main__':unittest.main()
