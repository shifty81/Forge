#!/usr/bin/env python3
from __future__ import annotations
import sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app"
if str(APP) not in sys.path:
    sys.path.insert(0,str(APP))

class ForgePYF742Tests(unittest.TestCase):
    def test_candidate_identity(self):
        from ForgeApplicationIdentity import DISPLAY_VERSION, DISPLAY_BUILD
        self.assertEqual(DISPLAY_VERSION,"0.5.0-candidate.777")
        self.assertEqual(DISPLAY_BUILD,"FORGEPY-F777")

    def test_dashboard_lazy_builder_resolves_forgepy_self(self):
        text=(APP/"ForgeProjectSurface.py").read_text(encoding="utf-8")
        self.assertIn("def _resolved_page",text)
        self.assertIn('return "ForgePY Self"',text)
        self.assertIn('actual=_resolved_page(gui,page)',text)
        self.assertIn('gui._show_page("Dashboard")',text)

    def test_green_publish_waits_for_gui_done_consumption(self):
        text=(APP/"ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("def _queue_green_publish_when_idle",text)
        self.assertIn("lambda: _queue_green_publish_when_idle",text)
        self.assertIn('bool(getattr(gui, "_busy", False)) or proc_running',text)
        # The worker-side completion observer must not directly call _after_green.
        branch=text.split('if command == "full":',1)[1].split('elif command in {"debug-bundle"',1)[0]
        self.assertNotIn('lambda: _after_green',branch)

    def test_failed_gate_debug_also_waits_for_idle(self):
        text=(APP/"ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("def _queue_failure_debug_when_idle",text)
        self.assertIn("_forge_full_gate_last_success_generation",text)

    def test_project_quickbar_is_project_aware_and_icon_capable(self):
        text=(APP/"ForgeUnifiedWorkflow.py").read_text(encoding="utf-8")
        branding=(APP/"ForgeProjectBranding.py").read_text(encoding="utf-8")
        self.assertIn("ForgeProjectBranding",text)
        self.assertIn('label_text = f"{project_name} · {context_suffix}"',text)
        self.assertIn("def discover_icon",branding)
        self.assertIn('root / "assets" / "branding" / f"{value}.png"',branding)

    def test_forgepy_icon_is_discovered_without_recursive_scan(self):
        from ForgeProjectBranding import discover_icon
        icon=discover_icon(ROOT,"ForgePY")
        self.assertIsNotNone(icon)
        self.assertEqual(icon.name,"ForgePY.png")

    def test_rust_successor_lane_is_forgepy_owned_and_non_authoritative(self):
        self.assertTrue((ROOT/"native"/"forge-rs"/"Cargo.toml").is_file())
        self.assertTrue((ROOT/"native"/"forge-rs"/"src"/"main.rs").is_file())
        lane=(ROOT/"tools"/"rust"/"ForgeRustLane.py").read_text(encoding="utf-8")
        self.assertIn('"authority": "python-forgepy"',lane)
        self.assertIn('"takeoverReady": False',lane)
        control=(ROOT/"project.control.json").read_text(encoding="utf-8")
        for key in ("audit.rust-migration","build.rust-forge","test.rust-forge","run.rust-forge"):
            self.assertIn(key,control)
        policy=(APP/"ForgePackagePolicy.py").read_text(encoding="utf-8")
        self.assertIn('"target"',policy)
        self.assertIn("TRANSIENT_ANYWHERE",policy)

if __name__=="__main__":
    unittest.main()
