from __future__ import annotations
import sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/'app'
if str(APP) not in sys.path:sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION,BUILD
import ForgeStartup
from ForgeToolProbe import probe_command
class Tests(unittest.TestCase):
    def test_identity(self):self.assertEqual((VERSION,BUILD),('0.4.415-F60R415','FORGEPY-F60R415'))
    def test_launchers(self):
        cmd=(ROOT/'ForgePY.cmd').read_text(encoding='utf-8'); dbg=(ROOT/'ForgePY-Debug.cmd').read_text(encoding='utf-8'); con=(ROOT/'ForgePYConsole.cmd').read_text(encoding='utf-8'); ver=(ROOT/'VerifyForgePY.cmd').read_text(encoding='utf-8')
        self.assertIn('ForgePY.vbs',cmd); self.assertIn('start "" /b wscript.exe',cmd); self.assertNotIn('python.exe "%FORGEPY_APP%" %*',cmd)
        self.assertIn('python.exe "%FORGEPY_APP%" %*',dbg); self.assertIn('pause',dbg.casefold())
        self.assertIn('--console',con); self.assertNotIn('call "%~dp0ForgePY.cmd"',con); self.assertIn('--self-test',ver); self.assertNotIn('call "%~dp0ForgePY.cmd"',ver)
    def test_startup_false_result_fails(self):
        with patch.object(ForgeStartup,'ensure_layout',return_value={'ok':True}),patch.object(ForgeStartup,'first_run_needed',return_value=False),patch.object(ForgeStartup,'diagnose',return_value={'ok':False}),patch.object(ForgeStartup,'repair_safe',return_value={'ok':False}):r=ForgeStartup.checks(None)
        self.assertFalse(r['ok'])
    def test_probe_python(self):self.assertTrue(probe_command([sys.executable],timeout=2)['ok'])
    def test_adapter_provider_wired(self):
        src=(APP/'PCCSurfaceCommon.py').read_text(encoding='utf-8'); self.assertIn('provider_mode = "forgepy-adapter"',src); self.assertTrue((APP/'ForgeGeneratedAdapterProvider.py').is_file())
    def test_tool_registry_delegates(self):
        src=(APP/'ForgeToolRegistry.py').read_text(encoding='utf-8'); self.assertIn('ForgeToolRuntime',src); self.assertNotIn('subprocess.Popen',src)
    def test_artifact_browser_indexed(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8'); start=src.index('    def _open_artifact_central_browser'); end=src.find('\n    def ',start+10); block=src[start:end]
        self.assertIn('artifact_index_search',block); self.assertNotIn('project_dir.rglob',block)
    def test_telemetry_reachable(self):
        src=(APP/'ForgeGui.py').read_text(encoding='utf-8'); a=src[src.index('    def _refresh_projects'):src.index('    def _refresh_project_health_async')]; b=src[src.index('    def _selected_project'):src.index('    def _project_selection_changed')]
        self.assertIn('forge_perf_record("projects.refresh"',a); self.assertNotIn('forge_perf_record',b)
if __name__=='__main__':unittest.main()
