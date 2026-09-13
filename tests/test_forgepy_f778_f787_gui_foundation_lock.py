from __future__ import annotations
import json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION

class ForgePYF778F787GuiFoundationLockTests(unittest.TestCase):
    def text(self, rel):
        return (ROOT/rel).read_text(encoding='utf-8')

    def test_candidate_identity(self):
        self.assertEqual(DISPLAY_BUILD,'FORGEPY-F797')
        self.assertEqual(DISPLAY_VERSION,'0.5.0-candidate.797')

    def test_protected_four_column_shell_has_project_context_rail(self):
        gui=self.text('native/forge-rs/src/gui/mod.rs')
        model=self.text('native/forge-rs/src/gui/model.rs')
        self.assertIn('forge-native-project-context-rail',gui)
        self.assertIn('project_rail_collapsed',model)
        self.assertIn('ProjectSection::ALL',gui)
        self.assertIn('Forge Rail | Project Rail', self.text('CHANGELOG.md'))

    def test_project_navigation_is_persistent_and_tool_scoped(self):
        model=self.text('native/forge-rs/src/gui/model.rs')
        for token in ('Source','BuildTest','Updates','Diagnostics','Artifacts','ProjectTools'):
            self.assertIn(token,model)
        self.assertIn('active_project_section',model)
        self.assertIn('self.dock.open_or_focus(section.tab())',self.text('native/forge-rs/src/gui/mod.rs'))

    def test_forgedock_wraps_raw_dockstate_and_focuses_existing_tabs(self):
        dock=self.text('native/forge-rs/src/gui/docking.rs')
        self.assertIn('pub struct ForgeDock',dock)
        self.assertIn('find_tab(&tab)',dock)
        self.assertIn('set_active_tab(path)',dock)
        self.assertIn('set_focused_node_and_surface',dock)
        self.assertIn('open_or_focus_deduplicates_tabs',dock)

    def test_dock_visual_feedback_is_upgraded(self):
        widgets=self.text('native/forge-rs/src/gui/widgets.rs')
        self.assertIn('OverlayType::HighlightedAreas',widgets)
        self.assertIn('style.separator.extra_interact_width = 5.0',widgets)
        self.assertIn('style.tab.minimum_width = Some(96.0)',widgets)
        self.assertIn('style.overlay.max_button_size = 96.0',widgets)

    def test_widget_palette_is_searchable_and_layout_presets_include_development(self):
        gui=self.text('native/forge-rs/src/gui/mod.rs')
        model=self.text('native/forge-rs/src/gui/model.rs')
        self.assertIn('Search widgets…',gui)
        self.assertIn('LayoutPreset::Development',self.text('native/forge-rs/src/gui/docking.rs'))
        self.assertIn('Development',model)
        self.assertIn('Reset ForgePY Layout',gui)

    def test_project_dashboard_is_split_into_real_landing_surfaces(self):
        widgets=self.text('native/forge-rs/src/gui/widgets.rs')
        for fn in ('source_page','build_test','run_page','updates','diagnostics','artifacts','project_tools'):
            self.assertIn(f'fn {fn}',widgets)

    def test_project_tools_are_capability_aware(self):
        widgets=self.text('native/forge-rs/src/gui/widgets.rs')
        gui=self.text('native/forge-rs/src/gui/mod.rs')
        self.assertIn('has_internal_pcc',widgets)
        self.assertIn('section == ProjectSection::ProjectTools && !self.shared.has_internal_pcc()',gui)

    def test_parity_records_gui_foundation_lock(self):
        matrix=json.loads(self.text('native/forge-rs/parity/matrix.json'))
        self.assertEqual(matrix['candidate'],'FORGEPY-F797')
        self.assertEqual(matrix['nativeBuild'],'FORGE-NATIVE-PCC-ASSET-BRIDGE-0.7.0-F797')
        rows={r['capability']:r for r in matrix['rows']}
        self.assertEqual(rows['project-context-navigation']['state'],'PASS')
        self.assertEqual(rows['dock-widget-system']['state'],'PASS')
        self.assertFalse(matrix['takeoverReady'])

if __name__=='__main__': unittest.main()
