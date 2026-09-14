import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ToolingWorkbenchTests(unittest.TestCase):
    def text(self, rel):
        return (ROOT / rel).read_text(encoding='utf-8')

    def test_tooling_contract_is_fail_closed_and_queue_bound(self):
        contract=self.text('native/forge-rs/src/gui/contract.rs')
        for token in [
            'FORGE-NATIVE-TOOLING-WORKBENCH-1.0-F950',
            'VISUAL_CLI_IS_REGISTERED_COMMAND_ONLY: bool = true',
            'TOOLING_PRESET_IS_PANEL_COMPOSED: bool = true',
            'TOOL_CATALOG_IS_SHARED_WITH_CLI: bool = true',
            'TOOLING_EXECUTION_USES_FOREGROUND_QUEUE: bool = true',
            'ARBITRARY_SHELL_REMAINS_DISABLED_IN_SHADOW: bool = true',
        ]:
            self.assertIn(token,contract)

    def test_registered_command_catalog_is_typed_and_bounded(self):
        tooling=self.text('native/forge-rs/src/gui/tooling.rs')
        self.assertIn('pub static COMMANDS: [CommandDescriptor; 18]',tooling)
        for token in ['CommandCategory','CommandRisk','requires_internal_pcc','favorite_default','command_by_alias']:
            self.assertIn(token,tooling)
        for alias in ['"full"','"build"','"project.self-test"','"git-status"','"asset-hydrate"','"gate.rust-shadow"']:
            self.assertIn(alias,tooling)
        self.assertIn('arbitrary shell execution remains disabled',tooling.lower())

    def test_visual_cli_and_tool_catalog_share_state(self):
        gui=self.text('native/forge-rs/src/gui/mod.rs')
        tooling=self.text('native/forge-rs/src/gui/tooling.rs')
        self.assertIn('ToolingUiState',gui)
        self.assertIn('tooling: &mut self.tooling',gui)
        self.assertIn('tooling::render_catalog',gui)
        self.assertIn('tooling::render_cli',gui)
        self.assertIn('tooling::render_operations',gui)
        self.assertIn('favorites',tooling)
        self.assertIn('selected_id',tooling)
        self.assertIn('safe_alias_input',tooling)

    def test_tooling_execution_converges_on_shared_foreground_queue(self):
        tooling=self.text('native/forge-rs/src/gui/tooling.rs')
        self.assertIn('shared.submit(descriptor.label, descriptor.alias)',tooling)
        self.assertIn('shared.queue.active_snapshot()',tooling)
        self.assertIn('shared.queue.pending_snapshot()',tooling)
        self.assertIn('shared.queue.cancel_pending(row.id)',tooling)
        self.assertIn('shared.queue.clear_pending()',tooling)
        self.assertIn('shared.queue.stop_active()',tooling)

    def test_tooling_interface_is_composed_from_existing_panels(self):
        model=self.text('native/forge-rs/src/gui/model.rs')
        docking=self.text('native/forge-rs/src/gui/docking.rs')
        self.assertIn('Self::Tooling => "Tooling / CLI"',model)
        self.assertIn('LayoutPreset::Tooling =>',docking)
        for panel in ['ProjectCli','ProjectTools','OperationQueue','ProjectContext','ForgeConsole','Diagnostics','QuickActions']:
            self.assertIn(f'ToolPanel::{panel}',docking)
        self.assertNotIn('ToolPanel::CommandCenter',model)

    def test_project_navigation_exposes_cli_without_expanding_panel_registry(self):
        model=self.text('native/forge-rs/src/gui/model.rs')
        registry=self.text('native/forge-rs/src/gui/registry.rs')
        self.assertIn('ProjectTools, ProjectCli',model)
        self.assertIn('Self::ProjectCli => ToolPanel::ProjectCli',model)
        self.assertIn('pub const PANELS: [PanelDescriptor; 27]',registry)
        self.assertIn('FORGE-NATIVE-TOOL-REGISTRY-1.1-F950',registry)

    def test_standalone_tool_host_reuses_visual_cli_state(self):
        standalone=self.text('native/forge-rs/src/gui/standalone.rs')
        self.assertIn('ToolingUiState::default()',standalone)
        self.assertIn('tooling: &mut self.tooling',standalone)
        self.assertIn('PanelIntent::ProjectSection(section) => self.panel = section.tab()',standalone)

    def test_gui_parity_manifest_records_tooling_without_takeover_claim(self):
        data=json.loads(self.text('native/forge-rs/parity/gui-parity.json'))
        self.assertIn('toolingWorkbench',data)
        self.assertEqual(data['toolingWorkbench']['contract'],'FORGE-NATIVE-TOOLING-WORKBENCH-1.0-F950')
        self.assertTrue(data['toolingWorkbench']['registeredCommandsOnly'])
        self.assertTrue(data['toolingWorkbench']['sharedForegroundQueue'])
        self.assertFalse(data['takeoverReady'])

    def test_tooling_state_persists_with_interface_session(self):
        gui=self.text('native/forge-rs/src/gui/mod.rs')
        tooling=self.text('native/forge-rs/src/gui/tooling.rs')
        self.assertIn('forge-native-tooling-workbench-v1',gui)
        self.assertIn('get_value(storage, TOOLING_KEY)',gui)
        self.assertIn('set_value(storage, TOOLING_KEY, &self.tooling)',gui)
        self.assertIn('Serialize, Deserialize',tooling)

    def test_rust_parity_matrix_records_visual_cli_workbench(self):
        parity=self.text('native/forge-rs/src/parity.rs')
        self.assertIn('capability: "visual-cli-workbench"',parity)
        self.assertIn('ParityState::Pass',parity)

if __name__ == '__main__':
    unittest.main()
