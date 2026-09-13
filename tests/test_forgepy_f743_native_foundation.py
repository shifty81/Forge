from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class ForgePYF743NativeFoundationTests(unittest.TestCase):
    def test_candidate_identity_tracks_current_candidate(self):
        from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
        self.assertEqual(DISPLAY_VERSION, "0.5.0-candidate.797")
        self.assertEqual(DISPLAY_BUILD, "FORGEPY-F797")

    def test_project_contract_declares_project_icon_and_native_lane(self):
        data = json.loads((ROOT / "project.control.json").read_text(encoding="utf-8"))
        project = data.get("project") or {}
        self.assertEqual(project.get("icon"), "assets/branding/ForgePY.png")
        self.assertEqual(project.get("candidateBuild"), "FORGEPY-F797")
        keys = {row.get("key") for row in data.get("commands", []) if isinstance(row, dict)}
        self.assertTrue({
            "audit.rust-migration", "audit.rust-parity", "gate.rust-shadow",
            "build.rust-forge", "test.rust-forge", "run.rust-forge",
        }.issubset(keys))

    def test_native_foundation_is_real_module_tree_not_single_placeholder(self):
        src = ROOT / "native" / "forge-rs" / "src"
        expected = {"lib.rs", "main.rs", "identity.rs", "contracts.rs", "paths.rs", "operations.rs", "transactions.rs", "parity.rs"}
        self.assertTrue(expected.issubset({path.name for path in src.glob("*.rs")}))
        main = (src / "main.rs").read_text(encoding="utf-8")
        lib = (src / "lib.rs").read_text(encoding="utf-8")
        self.assertIn("--parity-json", main)
        self.assertIn("--self-test", main)
        self.assertIn("pub mod operations", lib)
        self.assertIn("pub mod transactions", lib)

    def test_machine_readable_parity_matrix_is_fail_closed(self):
        matrix = json.loads((ROOT / "native" / "forge-rs" / "parity" / "matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix.get("phase"), "SHADOW")
        self.assertEqual(matrix.get("candidate"), "FORGEPY-F797")
        self.assertFalse(matrix.get("takeoverReady"))
        states = {row.get("state") for row in matrix.get("rows", [])}
        self.assertIn("MISSING", states)
        self.assertIn("DIFFERENT", states)

    def test_native_takeover_is_fail_closed_in_shadow(self):
        identity = (ROOT / "native" / "forge-rs" / "src" / "identity.rs").read_text(encoding="utf-8")
        parity = (ROOT / "native" / "forge-rs" / "src" / "parity.rs").read_text(encoding="utf-8")
        self.assertIn("AuthorityPhase::Shadow", identity)
        self.assertIn("python_authority: true", identity)
        self.assertIn("Missing", parity)
        self.assertIn("Different", parity)
        self.assertIn("takeover_ready", parity)

    def test_python_full_gate_certifies_rust_when_toolchain_exists(self):
        gate = (ROOT / "tools" / "ForgeGate.py").read_text(encoding="utf-8")
        self.assertIn("def rust_shadow_check", gate)
        self.assertIn("rust_shadow_check, manifest_check", gate)
        self.assertIn("cargo/rustc not available", gate)
        self.assertIn('"gate"', (ROOT / "tools" / "rust" / "ForgeRustLane.py").read_text(encoding="utf-8"))

    def test_self_dashboard_exposes_native_migration_controls(self):
        gui = (ROOT / "app" / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn("Forge Native Rust Migration · SHADOW", gui)
        self.assertIn('"Rust Status"', gui)
        self.assertIn('"Parity Matrix"', gui)
        self.assertIn('"Rust SHADOW Gate"', gui)
        self.assertIn('"Build Native"', gui)
        self.assertIn('"Run Native"', gui)

    def test_f742_dashboard_and_completion_repairs_remain(self):
        surface = (ROOT / "app" / "ForgeProjectSurface.py").read_text(encoding="utf-8")
        simplified = (ROOT / "app" / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("activate_initial_dashboard", surface)
        self.assertIn("_resolved_page", surface)
        self.assertIn("_queue_green_publish_when_idle", simplified)
        self.assertIn("_queue_failure_debug_when_idle", simplified)


if __name__ == "__main__":
    unittest.main()
