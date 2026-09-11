from __future__ import annotations
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ForgePYVersion import VERSION, BUILD


class ForgePYF60R67Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION, "0.4.377-F60R377")
        self.assertEqual(BUILD, "FORGEPY-F60R377")

    def test_shared_root_destroys_splash_widgets_before_handoff(self):
        src = (APP / "ForgeStartup.py").read_text(encoding="utf-8")
        block = src[src.index("if keep_root:"):src.index("else:", src.index("if keep_root:"))]
        self.assertIn("frame.destroy()", block)
        self.assertIn("root.withdraw()", block)
        self.assertIn("root.quit()", block)
        self.assertLess(block.index("frame.destroy()"), block.index("root.quit()"))


if __name__ == "__main__":
    unittest.main()
