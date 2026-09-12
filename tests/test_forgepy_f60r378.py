
from __future__ import annotations
import subprocess, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))

import VaultIntake
from ForgePYVersion import VERSION, BUILD

PATCH_TEXT='''diff --git a/sample.txt b/sample.txt
index 3367afd..3e75765 100644
--- a/sample.txt
+++ b/sample.txt
@@ -1 +1 @@
-old
+new
'''

def init_repo(root:Path, text:str):
    root.mkdir(parents=True,exist_ok=True)
    subprocess.run(['git','init','-q',str(root)],check=True)
    (root/'sample.txt').write_text(text,encoding='utf-8')

class F60R378Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,'0.4.390-F60R390')
        self.assertEqual(BUILD,'FORGEPY-F60R390')

    def test_unified_diff_is_not_bound_to_active_project_hint(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); patch_file=td/'ordinary.patch'; patch_file.write_text(PATCH_TEXT,encoding='utf-8')
            details=VaultIntake.inspect_patch(patch_file,project_hint=td/'SomeOtherProject')
            self.assertEqual(details['project'],'unassigned')

    def test_unique_registered_project_wins_even_when_other_project_is_selected(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); a=td/'Havenwild-main'; b=td/'Cortex-Main'
            init_repo(a,'old\n'); init_repo(b,'different\n')
            patch_file=td/'change.patch'; patch_file.write_text(PATCH_TEXT,encoding='utf-8')
            entries=[SimpleNamespace(project_id='havenwild',name='Havenwild',root=a),SimpleNamespace(project_id='cortex',name='Cortex',root=b)]
            with patch.object(VaultIntake,'_registered_project_entries',return_value=entries):
                result=VaultIntake.resolve_patch_target(patch_file)
            self.assertEqual(result['status'],'RESOLVED')
            self.assertEqual(Path(result['targetRoot']),a.resolve())
            self.assertEqual(result['targetProject'],'havenwild')

    def test_ambiguous_unified_diff_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); a=td/'One'; b=td/'Two'
            init_repo(a,'old\n'); init_repo(b,'old\n')
            patch_file=td/'change.patch'; patch_file.write_text(PATCH_TEXT,encoding='utf-8')
            entries=[SimpleNamespace(project_id='one',name='One',root=a),SimpleNamespace(project_id='two',name='Two',root=b)]
            with patch.object(VaultIntake,'_registered_project_entries',return_value=entries):
                result=VaultIntake.resolve_patch_target(patch_file)
            self.assertEqual(result['status'],'AMBIGUOUS')
            self.assertEqual(len(result['matches']),2)

    def test_download_scan_does_not_pass_active_root_as_project_hint(self):
        src=(APP/'VaultIntake.py').read_text(encoding='utf-8')
        block=src[src.index('def scan_downloads'):src.index('def scan_intake')]
        self.assertIn('project_hint=None',block)
        self.assertNotIn('project_hint=active_root',block)

    def test_gui_global_patch_paths_do_not_use_active_project_for_approval(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('vault_available_globally',src)
        self.assertIn('vault_approve_available_globally',src)
        self.assertIn('vault_resolve_patch_target(source)',src)
        review=src[src.index('def queue_selected'):src.index('def route_selected')]
        self.assertNotIn('_activate_project(root)',review)

if __name__=='__main__': unittest.main()
