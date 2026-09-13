from __future__ import annotations
import hashlib, json, sys, tempfile, unittest, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))

from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
from PCCSurfaceCommon import BackendClient, ProjectContract
from PCCAutoAdapter import _prepare_argv
from ForgeProjectPCC import profile, root_patch_transports
import ForgeAssetResolver as assets

class ForgePYF788F797ProjectPccAssetBridgeTests(unittest.TestCase):
    def text(self, rel): return (ROOT/rel).read_text(encoding='utf-8')

    def _contract(self, root:Path)->None:
        (root/'project.control.json').write_text(json.dumps({
            'schema':'forge.project.v1',
            'project':{'id':'sample','name':'Sample','kind':'native-cpp'},
            'root_control_center':{'launcher':'SampleTools.cmd','machine_provider':'SampleTools.ps1'},
            'commands':[
                {'key':'project.status','label':'Status','executable':'pwsh','arguments':['-NoProfile','-File','SampleTools.ps1','-Action','status']},
                {'key':'gate.full','label':'Full','executable':'pwsh','arguments':['-NoProfile','-File','SampleTools.ps1','-Action','full']},
                {'key':'patch.apply','label':'Apply','executable':'pwsh','arguments':['-NoProfile','-File','SampleTools.ps1','-Action','apply']},
                {'key':'recovery.undo-last','label':'Undo','executable':'pwsh','arguments':['-NoProfile','-File','SampleTools.ps1','-Action','undo']},
            ],
        }),encoding='utf-8')
        (root/'SampleTools.ps1').write_text('param([string]$Action)\n',encoding='utf-8')
        (root/'SampleTools.cmd').write_text('@echo off\r\n',encoding='utf-8')

    def test_candidate_identity(self):
        self.assertEqual(DISPLAY_BUILD,'FORGEPY-F797')
        self.assertEqual(DISPLAY_VERSION,'0.5.0-candidate.797')

    def test_powershell_machine_provider_is_not_executed_through_python(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); self._contract(root)
            client=BackendClient(root,ProjectContract.load(root))
            self.assertEqual(client.provider_mode,'auto-contract')
            self.assertEqual(client.script.name,'PCCAutoAdapter.py')
            argv=_prepare_argv(root,'SampleTools.ps1',['-Action','status'])
            self.assertIn('-File',argv)
            self.assertIn('SampleTools.ps1',' '.join(argv))
            self.assertNotEqual(Path(argv[0]).name.casefold(),'python.exe')

    def test_internal_pcc_profile_owns_patch_and_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); self._contract(root)
            info=profile(root)
            self.assertTrue(info['hasInternalPcc'])
            self.assertTrue(info['hasPatchAuthority'])
            self.assertTrue(info['hasRecoveryAuthority'])
            self.assertTrue(info['nativePatchReady'])

    def test_root_patch_transport_is_preserved_for_project_native_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); self._contract(root)
            patch=root/'Sample_Update.patch'
            with zipfile.ZipFile(patch,'w') as z:
                z.writestr('PATCH_MANIFEST.json',json.dumps({'schema':'pcc.patch.v1','project':'sample','patchId':'SAMPLE-1','files':[{'path':'x.txt','operation':'write','sha256':'0'*64}]}))
            self.assertEqual(root_patch_transports(root),[patch.resolve()])
            host=self.text('app/PCCOperationHost.py')
            self.assertIn('Project-owned root-drop authority detected',host)
            self.assertIn('Explicit Apply Updates delegated',host)

    def test_asset_requirement_can_hydrate_exact_member_from_verified_backup(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); project=base/'project'; backups=base/'backups'; project.mkdir(); backups.mkdir()
            payload=b'asset-bytes-for-test'; digest=hashlib.sha256(payload).hexdigest()
            (project/'forge.assets.json').write_text(json.dumps({'schema':'forge.assets.v1','assets':[{'id':'planet','name':'various_planets.glb','sha256':digest,'destination':'cache/various_planets.glb'}]}),encoding='utf-8')
            archive=backups/'source-backup.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('sources/various_planets.glb',payload)
                z.writestr('FORGEPY_BACKUP_MANIFEST.json',json.dumps({'schema':'forgepy.backup.v1','files':[{'path':'sources/various_planets.glb','bytes':len(payload),'sha256':digest}]}))
            original=assets._backup_roots
            assets._backup_roots=lambda:[backups]
            try:
                result=assets.hydrate(project,apply=True)
            finally:
                assets._backup_roots=original
            self.assertEqual(result['missing'],0)
            self.assertEqual((project/'cache/various_planets.glb').read_bytes(),payload)
            self.assertEqual(result['actions'][0]['source']['authority'],'backup-catalog')

    def test_native_project_tools_expose_pcc_and_asset_actions(self):
        gui=self.text('native/forge-rs/src/gui/widgets.rs')
        for token in ('Launch Internal PCC','Apply Project Update','Asset Status','Hydrate Assets','Find Missing Assets'):
            self.assertIn(token,gui)

    def test_manual_routing_can_defer_to_project_native_review_without_weakening_universal_engine(self):
        intake=self.text('app/ForgePYIntake.py')
        self.assertIn('PROJECT_NATIVE_REVIEW',intake)
        self.assertIn('nativePatchReady',intake)
        gui=self.text('app/ForgeGui.py')
        self.assertIn('Route Patch to Internal PCC',gui)
        self.assertIn('vault_stage_project_native_patch',gui)

    def test_generated_package_manifest_is_not_a_self_update_preimage_blocker(self):
        from ForgePatchBuilder import build as build_patch
        from VaultPatchEngine import validate_transport
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)/'base'; target=Path(td)/'target'; live=Path(td)/'live'
            for folder in (base,target,live):
                (folder/'app').mkdir(parents=True)
                (folder/'app'/'ForgeStandalone.py').write_text('# marker\n',encoding='utf-8')
            (base/'app'/'x.py').write_text('VALUE=1\n',encoding='utf-8')
            (target/'app'/'x.py').write_text('VALUE=2\n',encoding='utf-8')
            (live/'app'/'x.py').write_text('VALUE=1\n',encoding='utf-8')
            (base/'FORGEPY_PACKAGE_MANIFEST.json').write_text('{"generation":1}\n',encoding='utf-8')
            (target/'FORGEPY_PACKAGE_MANIFEST.json').write_text('{"generation":2}\n',encoding='utf-8')
            (live/'FORGEPY_PACKAGE_MANIFEST.json').write_text('{"generation":999}\n',encoding='utf-8')
            patch=Path(td)/'update.patch'
            built=build_patch(base,target,patch,project='forgepy',base_build='OLD',target_build='NEW',target_version='next')
            paths=[row['path'] for row in built['manifest']['files']]
            self.assertNotIn('FORGEPY_PACKAGE_MANIFEST.json',paths)
            self.assertIn('app/x.py',paths)
            # Also prove compatibility with an older transport that still carried the generated
            # manifest row: only that row may drift; real source preimages remain strict.
            old_patch=Path(td)/'legacy.patch'
            old_manifest={
                'schema':'forge.patch.v1','project':'forgepy','patchId':'LEGACY-GENERATED-MANIFEST',
                'files':[
                    {'path':'FORGEPY_PACKAGE_MANIFEST.json','operation':'write','preSha256':hashlib.sha256(b'{"generation":1}\n').hexdigest(),'sha256':hashlib.sha256(b'{"generation":2}\n').hexdigest(),'bytes':17},
                    {'path':'app/x.py','operation':'write','preSha256':hashlib.sha256(b'VALUE=1\n').hexdigest(),'sha256':hashlib.sha256(b'VALUE=2\n').hexdigest(),'bytes':8},
                ]
            }
            with zipfile.ZipFile(old_patch,'w') as z:
                z.writestr('PATCH_MANIFEST.json',json.dumps(old_manifest))
                z.writestr('payload/FORGEPY_PACKAGE_MANIFEST.json','{"generation":2}\n')
                z.writestr('payload/app/x.py','VALUE=2\n')
            checked=validate_transport(old_patch,live)
            self.assertEqual(len(checked['files']),2)

    def test_parity_records_bridge_without_claiming_takeover(self):
        matrix=json.loads(self.text('native/forge-rs/parity/matrix.json'))
        rows={r['capability']:r for r in matrix['rows']}
        self.assertEqual(rows['internal-pcc-bridge']['state'],'DIFFERENT')
        self.assertEqual(rows['asset-dependency-resolution']['state'],'DIFFERENT')
        self.assertFalse(matrix['takeoverReady'])

if __name__=='__main__': unittest.main()
