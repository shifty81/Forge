from __future__ import annotations
import json, tempfile, unittest, sys, time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/'app'
if str(APP) not in sys.path:sys.path.insert(0,str(APP))

from ForgePYVersion import VERSION, BUILD
from ForgeCommandBus import CommandBus
from ForgeToolContracts import ToolContract,ParameterSpec,ExecutionPolicy,validate_values,resolved_values
from ForgeSourceAuthority import matrix,safe_branch_name
from ForgeVaultIntelligence import facets
from ForgeAutomationRuntime import evaluate
from ForgeAutomationProfiles import AutomationProfile
from ForgeSettingsSchema import validate as validate_settings
from ForgeFirstRun import plan as first_run_plan
from ForgeStandaloneBuild import preflight

class F60R267Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,'0.4.379-F60R379'); self.assertEqual(BUILD,'FORGEPY-F60R379')
    def test_command_bus_metadata_and_unregister(self):
        b=CommandBus(); b.register('x',lambda:4,category='test',mutates=True); self.assertEqual(b.execute('x').value,4)
        self.assertTrue(b.specs()[0].mutates); self.assertTrue(b.unregister('x')); self.assertFalse(b.execute('x').ok)
    def test_typed_tool_coercion_and_confinement(self):
        c=ToolContract('x','build',(ParameterSpec('jobs','int',required=True),ParameterSpec('root','path',project_confined=True)))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); self.assertEqual(validate_values(c,{'jobs':'4','root':str(root/'a')},project_root=root),[])
            self.assertEqual(resolved_values(c,{'jobs':'4','root':str(root/'a')})['jobs'],4)
            self.assertTrue(validate_values(c,{'jobs':'4','root':str(root.parent)},project_root=root))
    def test_source_authority_matrix(self):
        self.assertEqual(matrix(working='a',head='a',green='a',forgegit='a',github='a')['state'],'SYNC')
        self.assertEqual(matrix(working='a',head='b')['state'],'DIVERGED')
        self.assertEqual(safe_branch_name(' Feature One '),'Feature-One')
    def test_vault_facets_duplicates(self):
        out=facets([{'classification':'Source','sha256':'x','path':'a'},{'classification':'Source','sha256':'x','path':'b'}])
        self.assertEqual(out['classifications']['Source'],2); self.assertEqual(out['duplicateGroups'][0]['count'],2)
    def test_automation_stays_disabled_by_default(self):
        p=AutomationProfile('x','X','p','gate.full',enabled=True,trigger='schedule')
        self.assertFalse(evaluate(p,{})['eligible']); self.assertTrue(evaluate(p,{'automationEnabled':True})['eligible'])
    def test_nonpatch_setting_cannot_be_enabled(self):
        self.assertTrue(validate_settings({'intake':{'archiveNonPatchArtifacts':True}}))
    def test_first_run_never_auto_installs_or_moves_nonpatch(self):
        with patch('ForgeFirstRun.needed',return_value=True):
            p=first_run_plan()
        self.assertFalse(p['automaticInstalls']); self.assertFalse(p['nonPatchMoves'])
    def test_standalone_preflight_is_truthful_off_windows(self):
        info=preflight(ROOT)
        if not sys.platform.startswith('win'): self.assertFalse(info['readyForWindowsBuild'])
    def test_job_queue_persistence_does_not_copy_thread_locks(self):
        from ForgeJobs import JobQueue
        q=JobQueue(1); j=q.submit('persist',lambda cancel:7,'demo')
        q._futures[j.job_id].result(timeout=2)
        rows=q.snapshot(); self.assertEqual(rows[0]['result'],7); self.assertIn('cancelRequested',rows[0])
        q.shutdown()
    def test_next_100_document_has_exactly_100_passes(self):
        text=(ROOT/'docs'/'NEXT_100_PASSES_F208_F307.md').read_text(encoding='utf-8')
        self.assertEqual(sum(1 for i in range(208,308) if f'**F{i}' in text),100)
if __name__=='__main__':unittest.main()
