from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
from VaultBuildIdentity import build_identity, verify_manifest_preconditions


class ForgePYF766CandidateRoutingTests(unittest.TestCase):
    def test_candidate_identity_is_f766(self):
        self.assertEqual(DISPLAY_VERSION, "0.5.0-candidate.777")
        self.assertEqual(DISPLAY_BUILD, "FORGEPY-F777")

    def test_build_identity_prefers_candidate_but_preserves_certified_donor(self):
        identity = build_identity(ROOT)
        self.assertEqual(identity["projectVersion"], "0.5.0-candidate.777")
        self.assertEqual(identity["projectBuild"], "FORGEPY-F777")
        self.assertEqual(identity["candidateProjectVersion"], "0.5.0-candidate.777")
        self.assertEqual(identity["candidateProjectBuild"], "FORGEPY-F777")
        self.assertEqual(identity["certifiedProjectVersion"], "0.4.415-F60R415")
        self.assertEqual(identity["certifiedProjectBuild"], "FORGEPY-F60R415")
        self.assertEqual(identity["identityPhase"], "candidate")

    def test_next_candidate_precondition_routes_against_live_candidate(self):
        manifest = {"schema": "forge.patch.v1", "preconditions": {"projectBuild": "FORGEPY-F777"}}
        result = verify_manifest_preconditions(manifest, ROOT)
        self.assertEqual(result["status"], "PASS", result)
        self.assertFalse(result["mismatches"], result)

    def test_generic_certified_project_still_uses_normal_build_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "project.control.json").write_text(json.dumps({
                "schema": "forge.project.v1",
                "project": {"id": "demo", "name": "Demo", "version": "1.2.3", "build": "DEMO-123"},
            }), encoding="utf-8")
            identity = build_identity(root)
            self.assertEqual(identity["projectVersion"], "1.2.3")
            self.assertEqual(identity["projectBuild"], "DEMO-123")
            self.assertEqual(identity["identityPhase"], "certified")

    def test_egui_036_theme_repair_is_cumulative(self):
        text = (ROOT / "native" / "forge-rs" / "src" / "gui" / "theme.rs").read_text(encoding="utf-8")
        self.assertIn("style_of(Theme::Dark)", text)
        self.assertIn("set_style_of(Theme::Dark", text)
        self.assertNotIn("ctx.style()", text)
        self.assertNotIn("ctx.set_style(style)", text)


if __name__ == "__main__":
    unittest.main()
