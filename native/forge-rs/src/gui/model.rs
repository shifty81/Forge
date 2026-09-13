use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum WorkspaceTab {
    Dashboard,
    ForgeConsole,
    OperationQueue,
    ProjectIntelligence,
    NativeMigration,
    ProjectCli,
    Vault,
    Workspace,
    Settings,
}

impl WorkspaceTab {
    pub const ALL: [Self; 9] = [
        Self::Dashboard,
        Self::ForgeConsole,
        Self::OperationQueue,
        Self::ProjectIntelligence,
        Self::NativeMigration,
        Self::ProjectCli,
        Self::Vault,
        Self::Workspace,
        Self::Settings,
    ];

    pub const fn title(self) -> &'static str {
        match self {
            Self::Dashboard => "Project",
            Self::ForgeConsole => "Forge Console",
            Self::OperationQueue => "Operations",
            Self::ProjectIntelligence => "Project Intelligence",
            Self::NativeMigration => "Native Migration",
            Self::ProjectCli => "Project CLI",
            Self::Vault => "Vault",
            Self::Workspace => "Workspace",
            Self::Settings => "Settings",
        }
    }

    pub const fn category(self) -> &'static str {
        match self {
            Self::Dashboard | Self::ProjectIntelligence | Self::ProjectCli => "Project",
            Self::ForgeConsole | Self::OperationQueue => "Operations",
            Self::Vault | Self::Workspace => "Workspace",
            Self::NativeMigration | Self::Settings => "System",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PrimarySurface {
    Vault,
    Project,
    Workspace,
    Settings,
}

impl PrimarySurface {
    pub const ALL: [Self; 4] = [Self::Vault, Self::Project, Self::Workspace, Self::Settings];

    pub const fn title(self) -> &'static str {
        match self {
            Self::Vault => "Vault",
            Self::Project => "Project",
            Self::Workspace => "Workspace",
            Self::Settings => "Settings",
        }
    }

    pub const fn tab(self) -> WorkspaceTab {
        match self {
            Self::Vault => WorkspaceTab::Vault,
            Self::Project => WorkspaceTab::Dashboard,
            Self::Workspace => WorkspaceTab::Workspace,
            Self::Settings => WorkspaceTab::Settings,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LayoutPreset {
    Forge,
    Operations,
    Intelligence,
}

impl LayoutPreset {
    pub const ALL: [Self; 3] = [Self::Forge, Self::Operations, Self::Intelligence];

    pub const fn title(self) -> &'static str {
        match self {
            Self::Forge => "Forge",
            Self::Operations => "Operations",
            Self::Intelligence => "Intelligence",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct PersistedShellState {
    pub active_surface: PrimarySurface,
    pub layout_locked: bool,
    pub compact_health: bool,
    pub preset: LayoutPreset,
}

impl Default for PersistedShellState {
    fn default() -> Self {
        Self {
            active_surface: PrimarySurface::Project,
            layout_locked: false,
            compact_health: false,
            preset: LayoutPreset::Forge,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn primary_surface_contract_matches_python_shell() {
        assert_eq!(PrimarySurface::ALL.map(|row| row.title()), ["Vault", "Project", "Workspace", "Settings"]);
    }

    #[test]
    fn project_surface_maps_to_dashboard() {
        assert_eq!(PrimarySurface::Project.tab(), WorkspaceTab::Dashboard);
    }

    #[test]
    fn widget_registry_is_semantically_grouped() {
        assert_eq!(WorkspaceTab::OperationQueue.category(), "Operations");
        assert_eq!(WorkspaceTab::ProjectIntelligence.category(), "Project");
        assert_eq!(WorkspaceTab::NativeMigration.category(), "System");
    }
}
