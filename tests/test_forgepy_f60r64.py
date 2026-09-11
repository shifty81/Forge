from __future__ import annotations
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ForgePYF60R64Tests(unittest.TestCase):
    def test_startup_done_state_persists_across_poll_ticks(self):
        src=(ROOT/"app/ForgeStartup.py").read_text(encoding="utf-8")
        self.assertIn("finished={'done':False}",src)
        self.assertIn("finished['done']=True",src)
        self.assertIn("if finished['done'] and",src)
        self.assertNotIn("done=False\n        while True:",src)

if __name__ == '__main__': unittest.main()
