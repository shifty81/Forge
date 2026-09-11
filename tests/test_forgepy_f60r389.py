from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];APP=ROOT/"app"
if str(APP) not in sys.path:sys.path.insert(0,str(APP))
from ForgePYVersion import VERSION,BUILD
class F60R389Tests(unittest.TestCase):
 def test_identity(self):self.assertEqual(VERSION,"0.4.389-F60R389");self.assertEqual(BUILD,"FORGEPY-F60R389")
 def test_app_wide_console(self):
  s=(APP/"ForgeGui.py").read_text();shell=s[s.index("def _build_shell"):s.index("def _build_projects_tab")];self.assertIn("_build_global_console",shell);self.assertIn("global_workspace_panes",shell)
 def test_console_command_input(self):
  s=(APP/"ForgeGui.py").read_text();self.assertIn("console_command_entry",s);self.assertIn("_console_show_suggestions",s);self.assertIn("<Control-space>",s);self.assertIn("self.contract.commands",s)
 def test_native_console_color(self):self.assertIn('widget.tag_configure("forgepy-native", foreground=CYAN)',(APP/"ForgeGui.py").read_text())
 def test_common_prompts_embedded(self):
  s=(APP/"ForgeGui.py").read_text();b=s[s.index("def _popup"):s.index("def _section_title")];self.assertNotIn("Toplevel",b);self.assertIn("_embedded_action_shell",b)
 def test_workspace_is_two_column_inside_global_shell(self):
  s=(APP/"ForgeGui.py").read_text();b=s[s.index("def _build_workspace_tab"):s.index("def _build_vault_tab")];self.assertNotIn("PROJECT CONSOLE",b);self.assertIn("panes.add(nav",b);self.assertIn("panes.add(center",b)
if __name__=="__main__":unittest.main()
