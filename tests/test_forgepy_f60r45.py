from __future__ import annotations
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "app" / "ForgeGui.py"
class ForgePYF60R45Tests(unittest.TestCase):
    def test_source_control_pane_order_and_scroll_contract(self):
        src = GUI.read_text(encoding="utf-8")
        build = src[src.index("def _build_source_control_tab"):src.index("def _build_forgejo_tab")]
        self.assertLess(build.index('self._panel(panes, "Actions")'), build.index('self._panel(panes, "Repository")'))
        self.assertLess(build.index('self._panel(panes, "Repository")'), build.index('self._panel(panes, "Branches / Tags")'))
        self.assertIn("action_body = self._make_scrollable_page(left)", build)
        self.assertIn('self._command_category_list(action_body, "Working Tree"', build)
        self.assertIn("self.source_branch_tree = ttk.Treeview(right,", build)
        self.assertIn("tag_box = tk.Frame(right,", build)
if __name__ == "__main__": unittest.main()
