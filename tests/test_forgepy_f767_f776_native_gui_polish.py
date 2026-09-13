import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ForgePYF767F776NativeGuiPolishTests(unittest.TestCase):
    def text(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_candidate_identity_is_f776(self):
        import sys
        sys.path.insert(0, str(ROOT / "app"))
        from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
        self.assertEqual(DISPLAY_BUILD, "FORGEPY-F777")
        self.assertEqual(DISPLAY_VERSION, "0.5.0-candidate.777")

    def test_native_wave2_identity(self):
        identity = self.text("native/forge-rs/src/identity.rs")
        self.assertIn('NATIVE_VERSION: &str = "0.5.0-shadow"', identity)
        self.assertIn('NATIVE_BUILD: &str = "FORGE-NATIVE-GUI-WAVE2-0.5.0-F776"', identity)
        lane = self.text("tools/rust/ForgeRustLane.py")
        self.assertIn('FORGEPY-RUST-LANE-0.5-F776', lane)

    def test_widget_registry_has_intelligence_and_operations(self):
        model = self.text("native/forge-rs/src/gui/model.rs")
        self.assertIn("OperationQueue", model)
        self.assertIn("ProjectIntelligence", model)
        self.assertIn('Self::OperationQueue => "Operations"', model)
        self.assertIn('Self::ProjectIntelligence => "Project Intelligence"', model)

    def test_layout_presets_and_lock_are_persisted(self):
        model = self.text("native/forge-rs/src/gui/model.rs")
        gui = self.text("native/forge-rs/src/gui/mod.rs")
        widgets = self.text("native/forge-rs/src/gui/widgets.rs")
        self.assertIn("LayoutPreset", model)
        self.assertIn("layout_locked", model)
        self.assertIn("dock_for_preset", widgets)
        self.assertIn("show_close_buttons(!self.shell.layout_locked)", gui)
        self.assertIn("draggable_tabs(!self.shell.layout_locked)", gui)
        self.assertIn("Lock dock layout", gui)

    def test_foreground_queue_is_visible_and_pending_jobs_can_cancel(self):
        ops = self.text("native/forge-rs/src/gui/operations.rs")
        widgets = self.text("native/forge-rs/src/gui/widgets.rs")
        self.assertIn("pending_snapshot", ops)
        self.assertIn("cancel_pending", ops)
        self.assertIn('heading(ui, "Foreground Operations"', widgets)
        self.assertIn('"Cancel queued"', widgets)
        self.assertIn('"Clear Pending Queue"', widgets)

    def test_zero_tooling_project_census_is_native_and_bounded(self):
        intel = self.text("native/forge-rs/src/intelligence.rs")
        self.assertIn("const MAX_ENTRIES: usize = 12_000", intel)
        self.assertIn("const MAX_DEPTH: usize = 4", intel)
        self.assertIn('"cargo.toml"', intel)
        self.assertIn('"cmakelists.txt"', intel)
        self.assertIn('"package.json"', intel)
        self.assertIn('"pyproject.toml"', intel)
        self.assertIn('"project.godot"', intel)
        self.assertIn("fn synthesize", intel)
        self.assertIn("generated_output_directories_are_not_descended", intel)

    def test_toolchain_intelligence_covers_primary_ecosystems(self):
        tools = self.text("native/forge-rs/src/toolchains.rs")
        for token in ['("git", "Git", "git")', '("cargo", "Rust Cargo", "cargo")', '("cmake", "CMake", "cmake")', '("dotnet", ".NET", "dotnet")', '("node", "Node.js", "node")', '("godot", "Godot", "godot")']:
            self.assertIn(token, tools)
        self.assertIn("env::split_paths", tools)

    def test_intelligence_is_visible_in_gui_and_headless_lane(self):
        widgets = self.text("native/forge-rs/src/gui/widgets.rs")
        main = self.text("native/forge-rs/src/main.rs")
        lane = self.text("tools/rust/ForgeRustLane.py")
        contract = json.loads(self.text("project.control.json"))
        self.assertIn('heading(ui, "Project Intelligence"', widgets)
        self.assertIn('"--intelligence-json"', main)
        self.assertIn('action == "intelligence"', lane)
        self.assertTrue(any(row.get("key") == "audit.rust-intelligence" for row in contract["commands"]))

    def test_quickbar_run_uses_governed_project_alias(self):
        gui = self.text("native/forge-rs/src/gui/mod.rs")
        adapter = self.text("app/PCCAutoAdapter.py")
        self.assertIn('"RUN" => self.shared.submit("Run", "launch-gui")', gui)
        self.assertIn('"launch-gui": ("run.gui", "run.game", "run.client", "run.editor", "run.runtime", "run.default")', adapter)

    def test_parity_matrix_records_wave2_without_claiming_takeover(self):
        matrix = json.loads(self.text("native/forge-rs/parity/matrix.json"))
        self.assertEqual(matrix["candidate"], "FORGEPY-F777")
        self.assertEqual(matrix["nativeBuild"], "FORGE-NATIVE-GUI-WAVE2-0.5.0-F776")
        self.assertFalse(matrix["takeoverReady"])
        rows = {row["capability"]: row for row in matrix["rows"]}
        self.assertEqual(rows["dock-widget-system"]["state"], "PASS")
        self.assertEqual(rows["operation-queue-ui"]["state"], "PASS")
        self.assertEqual(rows["project-intelligence"]["state"], "DIFFERENT")
        self.assertEqual(rows["catalog-storage"]["state"], "MISSING")


if __name__ == "__main__":
    unittest.main()
