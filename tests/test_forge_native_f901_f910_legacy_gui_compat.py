import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class LegacyGuiCompatibilityTests(unittest.TestCase):
    def text(self, rel):
        return (ROOT / rel).read_text(encoding='utf-8')

    def test_f755_f764_tokens_survive_panel_native_architecture(self):
        gui=self.text('native/forge-rs/src/gui/mod.rs')
        docking=self.text('native/forge-rs/src/gui/docking.rs')
        for token in ['FULL GATE','BUILD','TEST','RUN','REFRESH','PROJECT CLI','FORGEPY HEALTH','project_icon_uri','self.shared.project.icon','Reset ForgePY Layout']:
            self.assertIn(token,gui)
        self.assertIn('split_right(NodeIndex::root()',docking)

    def test_f778_f787_project_navigation_contract_maps_to_toolpanels(self):
        gui=self.text('native/forge-rs/src/gui/mod.rs')
        model=self.text('native/forge-rs/src/gui/model.rs')
        self.assertIn('forge-native-project-context-rail',gui)
        self.assertIn('project_rail_collapsed',model)
        self.assertIn('active_project_section',model)
        self.assertIn('ProjectSection::ALL',gui)
        self.assertIn('self.dock.open_or_focus(section.tab())',gui)
        self.assertIn('section == ProjectSection::ProjectTools && !self.shared.has_internal_pcc()',gui)

    def test_forgedock_legacy_focus_contract_is_real(self):
        docking=self.text('native/forge-rs/src/gui/docking.rs')
        for token in ['find_tab(&tab)','set_active_tab(path)','set_focused_node_and_surface','open_or_focus_deduplicates_tabs']:
            self.assertIn(token,docking)

    def test_legacy_palette_vocabulary_routes_to_new_registry(self):
        gui=self.text('native/forge-rs/src/gui/mod.rs')
        self.assertIn('Search widgets…',gui)
        self.assertIn('registry::find(&query)',gui)
        self.assertIn('Reset ForgePY Layout',gui)

    def test_panel_fallback_match_arm_returns_unit(self):
        gui=self.text('native/forge-rs/src/gui/mod.rs')
        self.assertIn('_ => { ui.label(RichText::new("Panel renderer unavailable").color(theme::RED)); }',gui)
        self.assertNotIn('_ => ui.label(RichText::new("Panel renderer unavailable").color(theme::RED)),',gui)

    def test_compatibility_does_not_restore_fixed_shell_authority(self):
        contract=self.text('native/forge-rs/src/gui/contract.rs')
        self.assertIn('PANEL_SYSTEM_IS_INTERFACE_AUTHORITY: bool = true',contract)
        self.assertIn('LEGACY_GUI_CERTIFICATION_COMPATIBLE: bool = true',contract)
        self.assertIn('FORGE-NATIVE-MODULAR-TOOLS-3.1-F910',contract)

if __name__ == '__main__':
    unittest.main()
