from __future__ import annotations
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class IntegrationAuditTests(unittest.TestCase):
    def test_gui_uses_runtime_service_hub(self):
        src=(ROOT/'app'/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('ForgeRuntimeServices',src); self.assertIn('self._runtime = ForgeRuntimeServices',src)
    def test_tool_ui_uses_governed_tool_runtime(self):
        src=(ROOT/'app'/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('forge_tool_execute(tool',src)
    def test_plugins_require_approval_when_enabled(self):
        src=(ROOT/'app'/'ForgePluginRegistry.py').read_text(encoding='utf-8')
        self.assertIn('approved:bool=False',src); self.assertIn('explicit approval',src)
    def test_backup_runtime_is_explicit_only(self):
        src=(ROOT/'app'/'ForgeBackupRuntime.py').read_text(encoding='utf-8')
        self.assertNotIn('schedule',src.casefold())
    def test_cumulative_notes_cover_f108_through_f307(self):
        text=(ROOT/'docs'/'history'/'passes'/'CUMULATIVE_PATCH_NOTES_F108_F307.md').read_text(encoding='utf-8')
        self.assertIn('F108–F207',text); self.assertIn('F208–F307',text)
if __name__=='__main__':unittest.main()
