
from __future__ import annotations
import sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app"
if str(APP) not in sys.path:
    sys.path.insert(0,str(APP))

from ForgePerformance import record, recent
from ForgePYVersion import VERSION, BUILD

class F60R376Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION,"0.4.389-F60R389")
        self.assertEqual(BUILD,"FORGEPY-F60R389")

    def test_perf_record_accepts_explicit_metadata(self):
        evt=record("projects.refresh",12.5,100.0,{"projects":9,"fullRescan":False})
        self.assertEqual(evt.threshold_ms,100.0)
        self.assertEqual(evt.metadata["projects"],9)

    def test_perf_record_is_backward_safe_if_mapping_is_third_argument(self):
        evt=record("legacy-call",8.0,{"projects":3})
        self.assertEqual(evt.threshold_ms,100.0)
        self.assertEqual(evt.metadata,{"projects":3})

    def test_project_refresh_call_uses_numeric_threshold(self):
        src=(APP/"ForgeGui.py").read_text(encoding="utf-8")
        expected='forge_perf_record("projects.refresh", (time.perf_counter() - perf_started) * 1000.0, 100.0, {"fullRescan": bool(full_rescan), "projects": len(entries)})'
        self.assertIn(expected,src)

if __name__=="__main__":
    unittest.main()
