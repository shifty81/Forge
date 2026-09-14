import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ForgeNativePanelInterfaceTests(unittest.TestCase):
    def text(self, rel: str) -> str:
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_panel_graph_is_interface_authority(self):
        contract = self.text("native/forge-rs/src/gui/contract.rs")
        self.assertIn("PANEL_SYSTEM_IS_INTERFACE_AUTHORITY: bool = true", contract)
        self.assertIn("ALL_FORGEPY_SURFACES_ARE_TOOL_PANELS: bool = true", contract)
        self.assertIn("PANELS_ARE_NESTABLE: bool = true", contract)
        self.assertIn("INTERFACES_ARE_SAVEABLE: bool = true", contract)
        self.assertIn("INTERFACES_ARE_LOCKABLE: bool = true", contract)
        self.assertIn("FORGEPY_MIRROR_PRESET_EXISTS: bool = true", contract)

    def test_registry_contains_all_forgepy_authority_panels(self):
        model = self.text("native/forge-rs/src/gui/model.rs")
        self.assertIn("pub const ALL: [Self; 27]", model)
        for token in [
            "ForgeNavigator", "ProjectNavigator", "QuickActions", "Overview", "Source",
            "BuildTest", "Run", "Updates", "Recovery", "Diagnostics", "Artifacts",
            "ProjectTools", "ProjectCli", "ProjectIntelligence", "NativeMigration",
            "AssetDependencies", "ForgeConsole", "OperationQueue", "ProjectHealth",
            "PatchIntake", "ProjectContext", "RecentActivity", "Vault", "Workspace",
            "Settings", "InterfaceManager", "Status",
        ]:
            self.assertIn(token, model)

    def test_forgepy_mirror_is_a_built_in_locked_preset_not_hardcoded_shell(self):
        model = self.text("native/forge-rs/src/gui/model.rs")
        docking = self.text("native/forge-rs/src/gui/docking.rs")
        self.assertIn('Self::Forge => "ForgePY Mirror"', model)
        self.assertIn("matches!(self, Self::Forge)", model)
        self.assertIn("fn forgepy_mirror() -> DockState<ToolPanel>", docking)
        for panel in [
            "ToolPanel::ForgeNavigator", "ToolPanel::ProjectNavigator", "ToolPanel::QuickActions",
            "ToolPanel::ForgeConsole", "ToolPanel::ProjectHealth", "ToolPanel::PatchIntake",
            "ToolPanel::ProjectContext", "ToolPanel::Status",
        ]:
            self.assertIn(panel, docking)

    def test_every_panel_can_nest_in_the_same_dock_graph(self):
        docking = self.text("native/forge-rs/src/gui/docking.rs")
        self.assertIn("DockState<ToolPanel>", docking)
        self.assertIn("split_right", docking)
        self.assertIn("split_left", docking)
        self.assertIn("split_above", docking)
        self.assertIn("split_below", docking)
        self.assertNotIn("if tab == WorkspaceTab::ForgeConsole", docking)

    def test_custom_interfaces_persist_layout_and_lock(self):
        interfaces = self.text("native/forge-rs/src/gui/interfaces.rs")
        gui = self.text("native/forge-rs/src/gui/mod.rs")
        self.assertIn("pub struct SavedInterface", interfaces)
        self.assertIn("pub dock: DockState<ToolPanel>", interfaces)
        self.assertIn("pub locked: bool", interfaces)
        self.assertIn("Save Current Interface", gui)
        self.assertIn("Save / Update", gui)
        self.assertIn("INTERFACE_LIBRARY_KEY", gui)

    def test_lock_disables_structural_dock_editing(self):
        gui = self.text("native/forge-rs/src/gui/mod.rs")
        self.assertIn("show_close_buttons(!self.shell.layout_locked)", gui)
        self.assertIn("draggable_tabs(!self.shell.layout_locked)", gui)
        self.assertIn("tab_context_menus(!self.shell.layout_locked)", gui)
        self.assertIn("show_leaf_collapse_buttons(!self.shell.layout_locked)", gui)
        self.assertIn("style.separator.extra_interact_width = 0.0", gui)

    def test_gui_parity_manifest_is_panel_native_and_not_takeover_ready(self):
        data = json.loads(self.text("native/forge-rs/parity/gui-parity.json"))
        self.assertIn(data["architecture"], {"panel-native-interface-graph", "modular-tool-panel-interface-graph"})
        self.assertEqual(data["defaultPreset"], "ForgePY Mirror")
        self.assertTrue(data["panels"]["nestable"])
        self.assertTrue(data["interfaces"]["saveable"])
        self.assertTrue(data["interfaces"]["lockable"])
        self.assertFalse(data["takeoverReady"])


if __name__ == "__main__":
    unittest.main()
