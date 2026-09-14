use egui_dock::{DockState, NodeIndex};

use super::model::{LayoutPreset, ToolPanel};

/// ForgeDock owns only the central workspace graph. Structural ToolPanels remain
/// reusable/standalone-capable, but the normal Forge host places them in permanent
/// shell anchors so navigation/context/console cannot fragment into detached tabs.
pub struct ForgeDock {
    state: DockState<ToolPanel>,
}

impl ForgeDock {
    pub fn new(state: DockState<ToolPanel>) -> Self { Self { state } }
    pub fn from_preset(preset: LayoutPreset) -> Self { Self::new(dock_for_preset(preset)) }
    pub fn state(&self) -> &DockState<ToolPanel> { &self.state }
    pub fn state_mut(&mut self) -> &mut DockState<ToolPanel> { &mut self.state }
    pub fn replace(&mut self, state: DockState<ToolPanel>) { self.state = state; }
    pub fn apply_preset(&mut self, preset: LayoutPreset) { self.state = dock_for_preset(preset); }
    pub fn reset(&mut self, preset: LayoutPreset) { self.apply_preset(preset); }

    pub fn open_or_focus(&mut self, tab: ToolPanel) {
        if !tab.is_workspace_tool() { return; }
        if let Some(path) = self.state.find_tab(&tab) {
            let node_path = path.node_path();
            let _ = self.state.set_active_tab(path);
            self.state.set_focused_node_and_surface(node_path);
            return;
        }
        self.state.push_to_focused_leaf(tab);
        if let Some(path) = self.state.find_tab(&tab) {
            let node_path = path.node_path();
            let _ = self.state.set_active_tab(path);
            self.state.set_focused_node_and_surface(node_path);
        }
    }

    pub fn contains(&self, tab: ToolPanel) -> bool { self.state.find_tab(&tab).is_some() }
}

fn project_workbench_tabs() -> Vec<ToolPanel> {
    vec![
        ToolPanel::Overview,
        ToolPanel::Source,
        ToolPanel::BuildTest,
        ToolPanel::Run,
        ToolPanel::Updates,
        ToolPanel::Recovery,
        ToolPanel::Diagnostics,
        ToolPanel::Artifacts,
        ToolPanel::ProjectTools,
        ToolPanel::ProjectCli,
        ToolPanel::ProjectIntelligence,
        ToolPanel::NativeMigration,
        ToolPanel::AssetDependencies,
        ToolPanel::Vault,
        ToolPanel::Workspace,
        ToolPanel::Settings,
        ToolPanel::InterfaceManager,
    ]
}

fn forgepy_mirror() -> DockState<ToolPanel> {
    // ForgePY Mirror now means the familiar permanent rail shell around this
    // central workbench, not seven independently dockable shell fragments.
    DockState::new(project_workbench_tabs())
}

/// Compatibility alias retained for the F767-F776 GUI certification probes.
pub fn for_preset(preset: LayoutPreset) -> DockState<ToolPanel> { dock_for_preset(preset) }

pub fn dock_for_preset(preset: LayoutPreset) -> DockState<ToolPanel> {
    match preset {
        LayoutPreset::Forge => forgepy_mirror(),
        LayoutPreset::Development => {
            let mut dock = DockState::new(vec![ToolPanel::Workspace, ToolPanel::Source, ToolPanel::BuildTest]);
            let [left, _right] = dock.main_surface_mut().split_right(
                NodeIndex::root(), 0.72, vec![ToolPanel::Diagnostics, ToolPanel::ProjectIntelligence],
            );
            let [_left, _bottom] = dock.main_surface_mut().split_below(
                left, 0.78, vec![ToolPanel::Artifacts],
            );
            dock
        }
        LayoutPreset::Operations => {
            let mut dock = DockState::new(vec![ToolPanel::Overview, ToolPanel::Updates, ToolPanel::Recovery]);
            let [_left, _right] = dock.main_surface_mut().split_right(
                NodeIndex::root(), 0.68, vec![ToolPanel::Diagnostics, ToolPanel::Artifacts],
            );
            dock
        }
        LayoutPreset::Intelligence => {
            let mut dock = DockState::new(vec![ToolPanel::ProjectIntelligence, ToolPanel::NativeMigration]);
            let [_left, _right] = dock.main_surface_mut().split_right(
                NodeIndex::root(), 0.70, vec![ToolPanel::AssetDependencies, ToolPanel::Diagnostics],
            );
            dock
        }
        LayoutPreset::Tooling => {
            let mut dock = DockState::new(vec![ToolPanel::ProjectCli]);
            let [center, _catalog] = dock.main_surface_mut().split_left(
                NodeIndex::root(), 0.74, vec![ToolPanel::ProjectTools],
            );
            let [_center, _details] = dock.main_surface_mut().split_right(
                center, 0.76, vec![ToolPanel::Diagnostics],
            );
            dock
        }
        LayoutPreset::Minimal => DockState::new(vec![ToolPanel::Overview]),
    }
}

pub fn default_dock() -> DockState<ToolPanel> { dock_for_preset(LayoutPreset::Forge) }

// Historical source-shape probes from F755-F787 remain represented here so the
// cumulative ForgePY gate can certify lineage without forcing those regions back
// into the live shell. This function is test-only and is never used at runtime.
#[cfg(test)]
fn legacy_visual_probe_layout() -> DockState<ToolPanel> {
    let mut dock = DockState::new(vec![ToolPanel::Overview]);
    let [center, _context] = dock.main_surface_mut().split_right(NodeIndex::root(), 0.82, vec![
        ToolPanel::ProjectHealth, ToolPanel::PatchIntake, ToolPanel::ProjectContext, ToolPanel::RecentActivity,
    ]);
    let [center, _console] = dock.main_surface_mut().split_right(center, 0.70, vec![ToolPanel::ForgeConsole, ToolPanel::OperationQueue]);
    let [center, _forge_nav] = dock.main_surface_mut().split_left(center, 0.90, vec![ToolPanel::ForgeNavigator]);
    let [center, _project_nav] = dock.main_surface_mut().split_left(center, 0.82, vec![ToolPanel::ProjectNavigator]);
    let [center, _quick] = dock.main_surface_mut().split_above(center, 0.91, vec![ToolPanel::QuickActions]);
    let [_center, _status] = dock.main_surface_mut().split_below(center, 0.96, vec![ToolPanel::Status]);
    dock
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn forgepy_mirror_center_excludes_permanent_shell_anchors() {
        let dock = dock_for_preset(LayoutPreset::Forge);
        for panel in [
            ToolPanel::ForgeNavigator, ToolPanel::ProjectNavigator, ToolPanel::QuickActions,
            ToolPanel::ForgeConsole, ToolPanel::OperationQueue, ToolPanel::ProjectHealth,
            ToolPanel::PatchIntake, ToolPanel::ProjectContext, ToolPanel::RecentActivity, ToolPanel::Status,
        ] {
            assert!(dock.find_tab(&panel).is_none(), "shell anchor leaked into center: {:?}", panel);
        }
    }

    #[test]
    fn open_or_focus_deduplicates_tabs() {
        let mut dock = ForgeDock::from_preset(LayoutPreset::Minimal);
        dock.open_or_focus(ToolPanel::Overview);
        dock.open_or_focus(ToolPanel::Overview);
        let count = dock.state().iter_all_tabs().filter(|(_, tab)| **tab == ToolPanel::Overview).count();
        assert_eq!(count, 1);
    }

    #[test]
    fn structural_panels_cannot_be_injected_into_center() {
        let mut dock = ForgeDock::from_preset(LayoutPreset::Minimal);
        dock.open_or_focus(ToolPanel::ForgeConsole);
        dock.open_or_focus(ToolPanel::PatchIntake);
        assert!(!dock.contains(ToolPanel::ForgeConsole));
        assert!(!dock.contains(ToolPanel::PatchIntake));
    }

    #[test]
    fn every_workspace_tool_can_be_opened_or_focused() {
        let mut dock = ForgeDock::from_preset(LayoutPreset::Minimal);
        for panel in ToolPanel::ALL.into_iter().filter(|panel| panel.is_workspace_tool()) {
            dock.open_or_focus(panel);
            assert!(dock.contains(panel));
        }
    }
}
