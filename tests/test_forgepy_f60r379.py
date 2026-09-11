from __future__ import annotations
import json,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/'app'
if str(APP) not in sys.path:sys.path.insert(0,str(APP))
from ForgePackagePolicy import is_governed,self_update_safe,classification
from ForgePatchBuilder import build
from ForgePYPatchEngine import validate_transport,PatchError
from ForgePYVersion import VERSION,BUILD

class F60R379Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,'0.4.379-F60R379');self.assertEqual(BUILD,'FORGEPY-F60R379')
    def test_runtime_state_is_never_governed_package_content(self):
        for p in ('logs/bootstrap/forgepy-bootstrap-latest.log','artifacts/x.zip','updates/inbox/a.patch','.forge/state.json','forgepy.settings.json'):
            self.assertFalse(is_governed(p),p)
        self.assertTrue(is_governed('app/ForgeGui.py'))
    def test_patch_builder_excludes_logs(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);a=td/'a';b=td/'b';a.mkdir();b.mkdir();(a/'app').mkdir();(b/'app').mkdir();(a/'logs').mkdir();(b/'logs').mkdir()
            (a/'app'/'x.py').write_text('a');(b/'app'/'x.py').write_text('b');(a/'logs'/'latest.log').write_text('old');(b/'logs'/'latest.log').write_text('new')
            out=td/'u.patch';r=build(a,b,out,target_build='FORGEPY-X')
            with zipfile.ZipFile(out) as z:m=json.loads(z.read('PATCH_MANIFEST.json'))
            paths=[x['path'] for x in m['files']]
            self.assertEqual(paths,['app/x.py'])
    def test_self_update_rejects_transient_target_before_preimage(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);root=td/'ForgePY';(root/'app').mkdir(parents=True);(root/'app'/'ForgePYStandalone.py').write_text('# marker')
            patch=td/'bad.patch';payload=b'bad';import hashlib
            manifest={'schema':'forge.patch.v1','engine':'forge-universal','project':'forgepy','patchId':'bad-self-update','files':[{'path':'logs/bootstrap/forgepy-bootstrap-latest.log','operation':'write','sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload),'preSha256':'0'*64}]}
            with zipfile.ZipFile(patch,'w') as z:z.writestr('PATCH_MANIFEST.json',json.dumps(manifest));z.writestr('payload/logs/bootstrap/forgepy-bootstrap-latest.log',payload)
            with self.assertRaisesRegex(PatchError,'unsafe ForgePY self-update target'):
                validate_transport(patch,root)
    def test_gui_preflights_self_update_queue(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('vault_validate_transport(source, target)',src)
        self.assertIn('vault_quarantine_queued_item',src)
if __name__=='__main__':unittest.main()
