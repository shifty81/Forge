from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'native/forge-rs/src/gui/model.rs'


class F976ShellAnchorCompileRepairTests(unittest.TestCase):
    def text(self):
        return MODEL.read_text(encoding='utf-8')

    def test_shell_anchor_has_one_trait_derive(self):
        model = self.text()
        anchor = re.search(r'(?P<prefix>(?:#\[derive\([^\n]+\)\]\s*)+)pub enum ShellAnchor', model)
        self.assertIsNotNone(anchor)
        derives = re.findall(r'#\[derive\(([^\n]+)\)\]', anchor.group('prefix'))
        self.assertEqual(len(derives), 1)
        for token in ('Debug', 'Clone', 'Copy', 'PartialEq', 'Eq', 'Hash', 'Serialize', 'Deserialize'):
            self.assertIn(token, derives[0])

    def test_toolpanel_owns_complete_trait_derive(self):
        model = self.text()
        panel = re.search(r'#\[derive\((?P<derive>[^\n]+)\)\]\s*pub enum ToolPanel', model)
        self.assertIsNotNone(panel)
        for token in ('Debug', 'Clone', 'Copy', 'PartialEq', 'Eq', 'Hash', 'Serialize', 'Deserialize'):
            self.assertIn(token, panel.group('derive'))

    def test_shell_anchor_insertion_does_not_steal_toolpanel_derive(self):
        model = self.text()
        shell_pos = model.index('pub enum ShellAnchor')
        panel_pos = model.index('pub enum ToolPanel')
        self.assertLess(shell_pos, panel_pos)
        window = model[panel_pos - 220:panel_pos]
        self.assertIn('#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]', window)


if __name__ == '__main__':
    unittest.main()
