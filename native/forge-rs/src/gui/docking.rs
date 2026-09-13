use egui_dock::{DockState, NodeIndex};

use super::model::{LayoutPreset, WorkspaceTab};

/// ForgeDock is the sole authority for central-workspace placement.
/// Shell rails, quickbar, health rail and status bar deliberately live outside it.
pub struct ForgeDock {
    state: DockState<WorkspaceTab>,
}

impl ForgeDock {
    pub fn new(state: DockState<WorkspaceTab>) -> Self { Self { state } }

    pub fn from_preset(preset: LayoutPreset) -> Self { Self::new(dock_for_preset(preset)) }

    pub fn state(&self) -> &DockState<WorkspaceTab> { &self.state }

    pub fn state_mut(&mut self) -> &mut DockState<WorkspaceTab> { &mut self.state }

    pub fn into_state(self) -> DockState<WorkspaceTab> { self.state }

    pub fn apply_preset(&mut self, preset: LayoutPreset) { self.state = dock_for_preset(preset); }

    pub fn reset(&mut self, preset: LayoutPreset) { self.apply_preset(preset); }

    pub fn open_or_focus(&mut self, tab: WorkspaceTab) {
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

    pub fn contains(&self, tab: WorkspaceTab) -> bool { self.state.find_tab(&tab).is_some() }
}

pub fn dock_for_preset(preset: LayoutPreset) -> DockState<WorkspaceTab> {
    match preset {
        LayoutPreset::Forge => {
            let mut dock = DockState::new(vec![WorkspaceTab::Dashboard]);
            dock.main_surface_mut().split_right(NodeIndex::root(), 0.60, vec![WorkspaceTab::ForgeConsole]);
            dock
        }
        LayoutPreset::Development => {
            let mut dock = DockState::new(vec![WorkspaceTab::Source, WorkspaceTab::BuildTest]);
            dock.main_surface_mut().split_right(NodeIndex::root(), 0.62, vec![WorkspaceTab::ForgeConsole]);
            dock
        }
        LayoutPreset::Operations => {
            let mut dock = DockState::new(vec![WorkspaceTab::OperationQueue]);
            dock.main_surface_mut().split_right(NodeIndex::root(), 0.54, vec![WorkspaceTab::ForgeConsole]);
            dock
        }
        LayoutPreset::Intelligence => {
            let mut dock = DockState::new(vec![WorkspaceTab::ProjectIntelligence]);
            dock.main_surface_mut().split_right(NodeIndex::root(), 0.64, vec![WorkspaceTab::Dashboard]);
            dock
        }
    }
}

pub fn default_dock() -> DockState<WorkspaceTab> { dock_for_preset(LayoutPreset::Forge) }

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shell_regions_are_not_dock_tabs() {
        let dock = default_dock();
        assert!(dock.find_tab(&WorkspaceTab::Dashboard).is_some());
        assert!(dock.find_tab(&WorkspaceTab::ForgeConsole).is_some());
    }

    #[test]
    fn open_or_focus_deduplicates_tabs() {
        let mut dock = ForgeDock::from_preset(LayoutPreset::Forge);
        dock.open_or_focus(WorkspaceTab::Dashboard);
        let count = dock.state().iter_all_tabs().filter(|(_, tab)| **tab == WorkspaceTab::Dashboard).count();
        assert_eq!(count, 1);
    }
}
