from __future__ import annotations
import json, tempfile, unittest, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION, BUILD
from ForgeEventBroker import EventBroker
from ForgeToolRegistry import ToolSpec
from ForgeToolScanner import activate
from ForgeToolchainDoctor import inspect
from ForgeVaultBootstrap import layout

class ForgePYF60R62Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,'0.4.379-F60R379'); self.assertEqual(BUILD,'FORGEPY-F60R379')
    def test_gui_keeps_health_rail_permanent_and_rebalances_workspace(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('workspaceConsoleRatio',src); self.assertIn('Compatibility no-op: F92',src)
        self.assertIn('lazy-tab:',src); self.assertIn('_persist_workspace_layout',src)
    def test_event_broker(self):
        b=EventBroker(); b.publish('x',{'a':1}); rows=b.drain(); self.assertEqual(rows[0].topic,'x')
    def test_tool_scanner_activates_python_script_and_declared_command(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tools').mkdir(); (root/'tools'/'build_world.py').write_text('print("ok")\n',encoding='utf-8')
            (root/'project.control.json').write_text(json.dumps({'schema':'forge.project.v1','project':{'id':'demo','name':'Demo','kind':'python'},'commands':[{'key':'gate.full','label':'Gate','program':'python','args':['x.py']}]}),encoding='utf-8')
            # Save location is redirected by calling scanner pieces through a minimal project id; scanner must at least classify without executing.
            result=activate(root,'demo-test')
            self.assertGreaterEqual(result['count'],2); self.assertTrue(any(t.capability=='build.all' for t in result['tools']))
            self.assertTrue(any(t.state=='VERIFIED' for t in result['tools']))
    def test_toolchain_doctor_is_structured(self):
        info=inspect(); self.assertIn('rows',info); self.assertTrue(any(r['tool']=='git' for r in info['rows']))
    def test_startup_and_tool_modules_exist(self):
        for name in ('ForgeStartup.py','ForgeFirstRun.py','ForgeVaultBootstrap.py','ForgeDriveCensus.py','ForgeRepair.py','ForgeToolRegistry.py','ForgeToolScanner.py','ForgeToolAdapters.py','ForgeToolchainDoctor.py','ForgeWorkers.py'):
            self.assertTrue((APP/name).is_file(),name)

if __name__=='__main__': unittest.main()
