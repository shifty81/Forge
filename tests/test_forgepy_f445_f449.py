from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import ForgeF440Normalization as norm
import ForgeSourceAuthority as authority


class ForgePYF445F449Tests(unittest.TestCase):
    def test_conflicting_patch_is_not_ready(self):
        a = {"state": "AVAILABLE", "patch_id": "PATCH-A", "manifest": {"conflictsWith": ["PATCH-B"]}}
        b = {"state": "APPLIED", "patch_id": "PATCH-B", "manifest": {}}
        bucket, reason = norm._policy_state(a, [a, b])
        self.assertEqual(bucket, "NEEDS ATTENTION")
        self.assertIn("PATCH-B", reason)

    def test_source_authority_allows_reference_mirror_but_fails_wrong_launcher(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app").mkdir()
            for name in ("ForgePYBootstrap.py", "ForgeGui.py", "ForgePYVersion.py"):
                (root / "app" / name).write_text("# canonical\n", encoding="utf-8")
            (root / "ForgePY.vbs").write_text("' gui\n", encoding="utf-8")
            (root / "ForgePY.cmd").write_text('set "FORGEPY_APP=%FORGEPY_HOME%app\\ForgePYBootstrap.py"\n', encoding="utf-8")
            mirror = root / "ForgePY" / "app"
            mirror.mkdir(parents=True)
            (mirror / "ForgeGui.py").write_text("# stale mirror\n", encoding="utf-8")
            report = authority.audit(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["mirrorState"], "diverged")
            self.assertTrue(report["warnings"])
            (root / "ForgePY.cmd").write_text('python ForgePY\\app\\ForgePYBootstrap.py\n', encoding="utf-8")
            report = authority.audit(root)
            self.assertFalse(report["ok"])

    def test_candidate_identity_remains_honest_until_green_promotion(self):
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertIn("FORGEPY-NORMALIZATION-F445-F449-CANDIDATE", source)
        self.assertIn("F445-F449-CANDIDATE", source)


if __name__ == "__main__":
    unittest.main()
