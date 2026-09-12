from __future__ import annotations
import json, tempfile, unittest, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION, BUILD
from ForgeCommandTaxonomy import category_for, group_commands
from ForgePagination import paginate
from ForgeRefreshCoordinator import RefreshCoordinator
from ForgeStateBroker import ProjectStateBroker
from ForgeConsoleBuffer import ConsoleBuffer
from ForgeVaultModel import classify
from ForgeToolContracts import ToolContract, ParameterSpec, validate_values
from ForgeSettingsSchema import validate as validate_settings
from ForgePluginRegistry import PluginSpec, validate as validate_plugin
from ForgeAdapterSDK import AdapterSpec, AdapterCommand, validate as validate_adapter
from ForgeCommandBus import CommandBus
from ForgeJobs import JobQueue
from ForgeReleaseModel import readiness
from ForgeCleanPcMatrix import scenarios

class ForgePYF60R167Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,'0.4.390-F60R390'); self.assertEqual(BUILD,'FORGEPY-F60R390')
    def test_command_taxonomy(self):
        self.assertEqual(category_for('gate.full'),'Test / Validation'); self.assertEqual(category_for('git.push'),'Source Control')
    def test_pagination(self):
        p=paginate(list(range(10)),offset=3,limit=4); self.assertEqual(p.items,(3,4,5,6)); self.assertTrue(p.has_more)
    def test_refresh_coordinator(self):
        r=RefreshCoordinator(); self.assertTrue(r.begin('x',0)); self.assertTrue(r.busy('x')); r.finish('x'); self.assertFalse(r.busy('x'))
    def test_state_broker(self):
        b=ProjectStateBroker(); s=b.update('p',git='PASS'); self.assertEqual(s.values['git'],'PASS'); self.assertGreater(s.generation,0)
    def test_console_buffer_is_bounded(self):
        b=ConsoleBuffer(1000); b.append('x\n'*1200); self.assertEqual(len(b),1000); self.assertEqual(len(b.search('x',10)),10)
    def test_vault_classification(self):
        self.assertEqual(classify('x/foo.patch'),'Patches'); self.assertEqual(classify('x/a.rs'),'Source'); self.assertEqual(classify('x/photo.png'),'Assets')
    def test_typed_tool_validation(self):
        c=ToolContract('x','build.all',(ParameterSpec('config',choices=('Debug','Release'),required=True),)); self.assertTrue(validate_values(c,{})); self.assertEqual(validate_values(c,{'config':'Debug'}),[])
    def test_settings_validation(self):
        self.assertEqual(validate_settings({'vaultHome':'D:/Vault','projectsRoot':'D:/Projects','artifactCentralRoot':'D:/Vault/ArtifactCentral','ui':{'workspaceConsoleRatio':.32}}),[])
    def test_plugin_permissions_fail_closed(self):
        self.assertTrue(validate_plugin(PluginSpec('x','X',permissions=('unknown',))))
    def test_adapter_validation(self):
        self.assertEqual(validate_adapter(AdapterSpec('a',commands=(AdapterCommand('build.all','cmake'),))),[])
    def test_command_bus(self):
        b=CommandBus(); b.register('x',lambda:3); self.assertEqual(b.execute('x').value,3); self.assertFalse(b.execute('missing').ok)
    def test_job_queue(self):
        q=JobQueue(1); j=q.submit('x',lambda cancel:42,'p'); q._futures[j.job_id].result(timeout=2); self.assertEqual(j.state,'PASS'); self.assertEqual(j.result,42)
    def test_release_readiness(self):
        self.assertFalse(readiness({'tests':True,'windows':False})['ready'])
    def test_clean_pc_matrix_has_offline_and_rollback(self):
        ids={x['id'] for x in scenarios()}; self.assertIn('offline',ids); self.assertIn('rollback',ids)
    def test_roadmap_has_exactly_100_passes(self):
        text=(ROOT/'docs'/'NEXT_100_PASSES_F108_F207.md').read_text(encoding='utf-8')
        self.assertEqual(sum(1 for i in range(108,208) if f'**F{i}' in text),100)

if __name__=='__main__': unittest.main()
