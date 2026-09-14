import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ModularToolHostTests(unittest.TestCase):
    def text(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_contract_locks_standalone_quality(self):
        text=self.text("native/forge-rs/src/gui/contract.rs")
        for token in [
            "PANEL_DESCRIPTOR_REGISTRY_COMPLETE: bool = true",
            "SAME_RENDERER_DOCKED_AND_STANDALONE: bool = true",
            "STANDALONE_TOOL_HOST_SUPPORTED: bool = true",
            "PANEL_IDS_ARE_STABLE: bool = true",
            "PANEL_SERVICES_ARE_PROJECT_BOUND: bool = true",
        ]:
            self.assertIn(token,text)

    def test_registry_covers_all_27_tools(self):
        registry=self.text("native/forge-rs/src/gui/registry.rs")
        model=self.text("native/forge-rs/src/gui/model.rs")
        self.assertIn("pub const PANELS: [PanelDescriptor; 27]",registry)
        self.assertIn("pub const fn slug",model)
        self.assertIn("pub fn from_slug",model)
        for token in ["preferred_size","minimum_size","maturity","standalone","singleton"]:
            self.assertIn(token,registry)

    def test_same_renderer_drives_docked_and_standalone_hosts(self):
        gui=self.text("native/forge-rs/src/gui/mod.rs")
        standalone=self.text("native/forge-rs/src/gui/standalone.rs")
        self.assertIn("pub(crate) struct ForgePanelViewer",gui)
        self.assertIn("host_kind: ToolHostKind",gui)
        self.assertIn("ForgePanelViewer",standalone)
        self.assertIn("ToolHostKind::Standalone",standalone)
        self.assertIn("ToolHostKind::Interface",gui)

    def test_tool_can_launch_from_main_binary_and_convenience_binary(self):
        main=self.text("native/forge-rs/src/main.rs")
        cargo=self.text("native/forge-rs/Cargo.toml")
        tool=self.text("native/forge-rs/src/bin/forge_tool.rs")
        self.assertIn('value_after(args, "--tool")',main)
        self.assertIn("run_native_tool",main)
        self.assertIn('name = "ForgeTool"',cargo)
        self.assertIn("ToolPanel::from_slug",tool)

    def test_tool_library_exposes_standalone_and_metadata(self):
        gui=self.text("native/forge-rs/src/gui/mod.rs")
        self.assertIn('RichText::new("Tool Library")',gui)
        self.assertIn('small_button("Standalone")',gui)
        self.assertIn('small_button("Open Standalone")',gui)
        self.assertIn("descriptor.maturity.label()",gui)
        self.assertIn("descriptor.summary",gui)

    def test_parity_manifest_records_modular_host_without_claiming_takeover(self):
        data=json.loads(self.text("native/forge-rs/parity/gui-parity.json"))
        self.assertEqual(data["contract"],"FORGE-NATIVE-MODULAR-TOOLS-3.0-F900")
        self.assertEqual(data["architecture"],"modular-tool-panel-interface-graph")
        self.assertTrue(data["panels"]["standaloneHost"])
        self.assertTrue(data["toolHost"]["sameRenderer"])
        self.assertFalse(data["takeoverReady"])

if __name__ == "__main__":
    unittest.main()
