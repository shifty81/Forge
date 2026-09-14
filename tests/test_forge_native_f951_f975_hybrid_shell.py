import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class HybridShellTests(unittest.TestCase):
    def text(self, rel): return (ROOT/rel).read_text(encoding='utf-8')

    def test_contract_locks_permanent_rails_and_console_cortex(self):
        c=self.text('native/forge-rs/src/gui/contract.rs')
        for token in [
            'FORGE-NATIVE-HYBRID-SHELL-1.0-F975',
            'PERMANENT_TOP_COMMAND_RAIL: bool = true',
            'PERMANENT_LEFT_NAVIGATION_RAIL: bool = true',
            'PERMANENT_RIGHT_CONTEXT_RAIL: bool = true',
            'PERMANENT_BOTTOM_CONSOLE_CORTEX_RAIL: bool = true',
            'PERMANENT_STATUS_RAIL: bool = true',
            'CENTRAL_DOCK_EXCLUDES_SHELL_ANCHORS: bool = true',
            'FORGE_CONSOLE_IS_PERMANENT: bool = true',
            'CORTEX_IS_EMBEDDED_IN_CONSOLE_RAIL: bool = true',
            'CORTEX_NATIVE_BRIDGE_REMAINS_SHADOW: bool = true',
        ]: self.assertIn(token,c)

    def test_model_maps_structural_tools_to_shell_anchors(self):
        m=self.text('native/forge-rs/src/gui/model.rs')
        for token in ['pub enum ShellAnchor','pub enum ContextRailTab','pub enum BottomRailTab','pub const fn shell_anchor','pub const fn is_workspace_tool']:
            self.assertIn(token,m)
        self.assertIn('Self::ForgeConsole | Self::OperationQueue => Some(ShellAnchor::BottomConsole)',m)
        self.assertIn('Self::ProjectHealth | Self::PatchIntake | Self::ProjectContext | Self::RecentActivity => Some(ShellAnchor::RightContext)',m)

    def test_live_shell_has_five_permanent_anchors(self):
        g=self.text('native/forge-rs/src/gui/mod.rs')
        for token in [
            'Panel::top("forge-native-command-rail")',
            'Panel::left("forge-native-navigation-rail")',
            'Panel::right("forge-native-context-rail")',
            'Panel::bottom("forge-native-console-cortex-rail")',
            'Panel::bottom("forge-native-status-rail")',
        ]: self.assertIn(token,g)
        self.assertIn('FORGE CONSOLE / CORTEX',g)
        self.assertIn('BottomRailTab::Cortex => self.draw_cortex_surface(ui)',g)

    def test_console_and_context_requests_route_to_rails(self):
        g=self.text('native/forge-rs/src/gui/mod.rs')
        self.assertIn('fn focus_panel(&mut self, panel: ToolPanel)',g)
        self.assertIn('Some(ShellAnchor::RightContext)',g)
        self.assertIn('Some(ShellAnchor::BottomConsole)',g)
        self.assertIn('ToolPanel::OperationQueue => BottomRailTab::Operations',g)
        self.assertIn('ToolPanel::PatchIntake => ContextRailTab::PatchIntake',g)

    def test_central_dock_rejects_shell_anchor_injection(self):
        d=self.text('native/forge-rs/src/gui/docking.rs')
        self.assertIn('if !tab.is_workspace_tool() { return; }',d)
        self.assertIn('structural_panels_cannot_be_injected_into_center',d)
        self.assertIn('forgepy_mirror_center_excludes_permanent_shell_anchors',d)

    def test_custom_interfaces_are_center_workspace_only(self):
        g=self.text('native/forge-rs/src/gui/mod.rs')
        self.assertIn('Save Current Interface / Center Workspace',g)
        self.assertIn('Permanent shell rails are not serialized into custom center layouts.',g)
        self.assertIn('forge-native-interface-library-v2',g)
        self.assertIn('forge-native-hybrid-workspace-v5',g)

    def test_parity_manifest_records_hybrid_shell_without_takeover(self):
        data=json.loads(self.text('native/forge-rs/parity/gui-parity.json'))
        self.assertEqual(data['hybridShell']['contract'],'FORGE-NATIVE-HYBRID-SHELL-1.0-F975')
        self.assertTrue(data['hybridShell']['bottomConsoleCortexRail']['permanent'])
        self.assertTrue(data['hybridShell']['bottomConsoleCortexRail']['consolePermanent'])
        self.assertEqual(data['hybridShell']['bottomConsoleCortexRail']['cortexBridge'],'SHADOW')
        self.assertTrue(data['hybridShell']['centralWorkspace']['excludesShellAnchors'])
        self.assertFalse(data['takeoverReady'])

if __name__=='__main__': unittest.main()
