import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ForgePYF755F764NativeGuiWaveTests(unittest.TestCase):
    def text(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_candidate_identity_is_f764(self):
        import sys
        sys.path.insert(0, str(ROOT / "app"))
        from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
        self.assertEqual(DISPLAY_BUILD, "FORGEPY-F797")
        self.assertEqual(DISPLAY_VERSION, "0.5.0-candidate.797")

    def test_native_gui_dependencies_are_pinned(self):
        cargo = self.text("native/forge-rs/Cargo.toml")
        self.assertIn('eframe = { version = "=0.36.2"', cargo)
        self.assertIn('egui_dock = { version = "=0.21.1"', cargo)
        self.assertIn('egui_extras = { version = "=0.36.2"', cargo)

    def test_native_default_launch_is_graphical(self):
        main = self.text("native/forge-rs/src/main.rs")
        self.assertIn("run_native_gui(root)", main)
        self.assertIn('arg == "--headless"', main)
        self.assertNotIn("println!(\"Forge Native Rust successor", main.split('if args.iter().any(|arg| arg == "--headless")')[0])

    def test_shell_recreates_primary_forgepy_chrome(self):
        gui = self.text("native/forge-rs/src/gui/mod.rs")
        for token in ["FULL GATE", "BUILD", "TEST", "RUN", "REFRESH", "PROJECT CLI", "FORGEPY HEALTH"]:
            self.assertIn(token, gui)
        model = self.text("native/forge-rs/src/gui/model.rs")
        for token in ["Vault", "Project", "Workspace", "Settings"]:
            self.assertIn(f'"{token}"', model)

    def test_dockable_widget_system_is_real(self):
        gui = self.text("native/forge-rs/src/gui/mod.rs")
        widgets = self.text("native/forge-rs/src/gui/widgets.rs")
        docking = self.text("native/forge-rs/src/gui/docking.rs")
        self.assertIn("DockArea::new", gui)
        self.assertIn("show_close_buttons(!self.shell.layout_locked)", gui)
        self.assertIn("draggable_tabs(!self.shell.layout_locked)", gui)
        self.assertIn("split_right(NodeIndex::root()", docking)
        self.assertIn("pub struct ForgeDock", docking)
        self.assertIn("open_or_focus", docking)
        self.assertIn("Reset ForgePY Layout", gui)
        self.assertIn("set_value(storage, DOCK_KEY", gui)

    def test_native_console_has_send_and_stop(self):
        widgets = self.text("native/forge-rs/src/gui/widgets.rs")
        self.assertIn('Button::new("Send")', widgets)
        self.assertIn('Button::new("Stop")', widgets)
        self.assertIn("stop_active()", widgets)
        self.assertIn("execute_console_command", widgets)

    def test_native_foreground_queue_is_single_flight_and_project_bound(self):
        queue = self.text("native/forge-rs/src/gui/operations.rs")
        self.assertIn("pending: VecDeque<QueuedOperation>", queue)
        self.assertIn("active: Option<ActiveOperation>", queue)
        self.assertIn("pub project_id: String", queue)
        self.assertIn("pub root: PathBuf", queue)
        self.assertIn("Duplicate request", self.text("native/forge-rs/src/gui/widgets.rs"))
        self.assertIn("taskkill", queue)

    def test_native_run_lane_launches_detached_gui(self):
        lane = self.text("tools/rust/ForgeRustLane.py")
        self.assertIn("FORGEPY-RUST-LANE-0.6-F787", lane)
        self.assertIn("def _launch_gui", lane)
        self.assertIn('"--gui"', lane)
        self.assertIn("subprocess.Popen", lane)
        self.assertIn("FORGEPY_PYTHON", lane)

    def test_project_icon_is_used_by_native_quickbar(self):
        gui = self.text("native/forge-rs/src/gui/mod.rs")
        self.assertIn("project_icon_uri", gui)
        self.assertIn("self.shared.project.icon", gui)
        contract = json.loads(self.text("project.control.json"))
        self.assertEqual(contract["project"]["icon"], "assets/branding/ForgePY.png")

    def test_shadow_cargo_lock_is_runtime_generated(self):
        policy = (ROOT / "app/ForgePackagePolicy.py").read_text(encoding="utf-8")
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn('native/forge-rs/Cargo.lock', policy)
        self.assertIn('native/forge-rs/Cargo.lock', ignore)
        # Cargo.lock is runtime-generated during SHADOW and may legitimately exist on
        # a developer machine after the first native build. Governance must ignore it;
        # the quality gate must not require the runtime file to be absent.
        import sys
        if str(ROOT / "app") not in sys.path:
            sys.path.insert(0, str(ROOT / "app"))
        from ForgePackagePolicy import classification
        self.assertEqual(classification("native/forge-rs/Cargo.lock"), "runtime-transient")

    def test_parity_matrix_records_native_gui_without_claiming_takeover(self):
        matrix = json.loads(self.text("native/forge-rs/parity/matrix.json"))
        self.assertEqual(matrix["candidate"], "FORGEPY-F797")
        self.assertEqual(matrix["nativeBuild"], "FORGE-NATIVE-PCC-ASSET-BRIDGE-0.7.0-F797")
        self.assertFalse(matrix["takeoverReady"])
        rows = {row["capability"]: row for row in matrix["rows"]}
        self.assertEqual(rows["dock-widget-system"]["state"], "PASS")
        self.assertEqual(rows["native-gui"]["state"], "DIFFERENT")
        self.assertEqual(rows["foreground-operation-queue"]["state"], "DIFFERENT")


if __name__ == "__main__":
    unittest.main()
