from __future__ import annotations
import json,sqlite3,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];APP=ROOT/'app'
if str(APP) not in sys.path:sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION,BUILD
from ForgeVersionConstraints import satisfies
from ForgeToolForms import form_model,cli_args
from ForgeToolContracts import ToolContract,ParameterSpec,OutputSpec
from ForgeVaultOwnership import score,classify_confidence
from ForgeGitConflict import parse_porcelain,resolution_plan
from ForgeRestoreTransaction import plan as restore_plan
from ForgeScheduler import Schedule,tick
from ForgeNotifications import Notice,NoticeCenter
from ForgeSecurityV2 import redact,safe_env
from ForgeMigrations import Migration,apply_all,current
from ForgeHealthV3 import aggregate
from ForgeUiMetrics import WorkspaceMetrics
from ForgeCommandAvailability import matrix
class F60R367Tests(unittest.TestCase):
    def test_identity(self):self.assertEqual(VERSION,'0.4.377-F60R377');self.assertEqual(BUILD,'FORGEPY-F60R377')
    def test_version_constraints(self):
        self.assertTrue(satisfies('4.2.1','>=4.0,<5'));self.assertFalse(satisfies('3.9','>=4.0'));self.assertTrue(satisfies('4.2.8','~4.2'))
    def test_tool_form_model(self):
        c=ToolContract('x','build',(ParameterSpec('jobs','int',True),ParameterSpec('clean','bool'),), (OutputSpec('log','artifact','logs/*.log'),))
        m=form_model(c);self.assertEqual(m['fields'][0]['widget'],'number');self.assertEqual(cli_args(c,{'jobs':4,'clean':True}),['--jobs','4','--clean'])
    def test_vault_ownership_score(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'Project';root.mkdir();p=root/'a.txt';p.write_text('x')
            rows=score(p,[{'root':str(root),'projectId':'p'}]);self.assertEqual(classify_confidence(rows),'high')
    def test_conflict_model(self):
        rows=parse_porcelain('UU app/a.py\n M b.py');self.assertEqual(rows[0]['path'],'app/a.py');self.assertFalse(resolution_plan('app/a.py','ours')['automatic'])
    def test_scheduler_disabled_unless_global_enabled(self):
        s=Schedule('x',60,True,0);seen=[];self.assertEqual(tick([s],seen.append,global_enabled=False,now=1000),[]);self.assertEqual(tick([s],seen.append,global_enabled=True,now=1000),['x'])
    def test_notice_dedupe(self):
        c=NoticeCenter();n=Notice('a','A','x',dedupe_key='same');self.assertTrue(c.publish(n));self.assertFalse(c.publish(n))
    def test_redaction(self):
        self.assertNotIn('abc123',redact('token=abc123'));self.assertNotIn('TOKEN', ' '.join(safe_env({'PATH':'x','TOKEN':'secret'}).keys()))
    def test_migrations(self):
        db=sqlite3.connect(':memory:');m=Migration(1,'a',lambda d:d.execute('CREATE TABLE x(v INTEGER)'));self.assertEqual(apply_all(db,[m]),[1]);self.assertEqual(current(db),1)
    def test_health(self):self.assertEqual(aggregate({'a':'PASS','b':'WARN'})['overall'],'WARN')
    def test_workspace_metrics(self):self.assertGreater(WorkspaceMetrics().normalized(1920)['controls'],0)
    def test_command_availability(self):self.assertTrue(matrix([{'key':'x','requires':['git']}],{'git'})[0]['available'])
    def test_next_100_has_exactly_100(self):
        text=(ROOT/'docs'/'NEXT_100_PASSES_F308_F407.md').read_text(encoding='utf-8');self.assertEqual(sum(1 for i in range(308,408) if f'**F{i}' in text),100)
if __name__=='__main__':unittest.main()
