use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum WorkspaceTab {
    Dashboard,
    Source,
    BuildTest,
    Run,
    Updates,
    ProjectIntelligence,
    NativeMigration,
    Diagnostics,
    Artifacts,
    ProjectTools,
    ForgeConsole,
    OperationQueue,
    ProjectCli,
    Vault,
    Workspace,
    Settings,
}

impl WorkspaceTab {
    pub const ALL: [Self; 16] = [
        Self::Dashboard,
        Self::Source,
        Self::BuildTest,
        Self::Run,
        Self::Updates,
        Self::ProjectIntelligence,
        Self::NativeMigration,
        Self::Diagnostics,
        Self::Artifacts,
        Self::ProjectTools,
        Self::ForgeConsole,
        Self::OperationQueue,
        Self::ProjectCli,
        Self::Vault,
        Self::Workspace,
        Self::Settings,
    ];

    pub const fn title(self) -> &'static str {
        match self {
            Self::Dashboard => "Overview",
            Self::Source => "Source",
            Self::BuildTest => "Build & Test",
            Self::Run => "Run",
            Self::Updates => "Updates",
            Self::ProjectIntelligence => "Intelligence",
            Self::NativeMigration => "Native",
            Self::Diagnostics => "Diagnostics",
            Self::Artifacts => "Artifacts",
            Self::ProjectTools => "Project Tools",
            Self::ForgeConsole => "Forge Console",
            Self::OperationQueue => "Operations",
            Self::ProjectCli => "Project CLI",
            Self::Vault => "Vault",
            Self::Workspace => "Workspace",
            Self::Settings => "Settings",
        }
    }

    pub const fn category(self) -> &'static str {
        match self {
            Self::Dashboard
            | Self::Source
            | Self::BuildTest
            | Self::Run
            | Self::Updates
            | Self::ProjectIntelligence
            | Self::NativeMigration
            | Self::Diagnostics
            | Self::Artifacts
            | Self::ProjectTools
            | Self::ProjectCli => "Project",
            Self::ForgeConsole | Self::OperationQueue => "Operations",
            Self::Vault | Self::Workspace => "Workspace",
            Self::Settings => "System",
        }
    }

    pub const fn icon(self) -> &'static str {
        match self {
            Self::Dashboard => "◆",
            Self::Source => "⌘",
            Self::BuildTest => "⚒",
            Self::Run => "▶",
            Self::Updates => "⇣",
            Self::ProjectIntelligence => "◎",
            Self::NativeMigration => "N",
            Self::Diagnostics => "!",
            Self::Artifacts => "◇",
            Self::ProjectTools => "⋮",
            Self::ForgeConsole => ">_",
            Self::OperationQueue => "≡",
            Self::ProjectCli => ">",
            Self::Vault => "V",
            Self::Workspace => "W",
            Self::Settings => "S",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProjectSection {
    Overview,
    Source,
    BuildTest,
    Run,
    Updates,
    Intelligence,
    Native,
    Diagnostics,
    Artifacts,
    ProjectTools,
}

impl ProjectSection {
    pub const ALL: [Self; 10] = [
        Self::Overview,
        Self::Source,
        Self::BuildTest,
        Self::Run,
        Self::Updates,
        Self::Intelligence,
        Self::Native,
        Self::Diagnostics,
        Self::Artifacts,
        Self::ProjectTools,
    ];

    pub const fn title(self) -> &'static str {
        match self {
            Self::Overview => "Overview",
            Self::Source => "Source",
            Self::BuildTest => "Build & Test",
            Self::Run => "Run",
            Self::Updates => "Updates",
            Self::Intelligence => "Intelligence",
            Self::Native => "Native",
            Self::Diagnostics => "Diagnostics",
            Self::Artifacts => "Artifacts",
            Self::ProjectTools => "Project Tools",
        }
    }

    pub const fn tab(self) -> WorkspaceTab {
        match self {
            Self::Overview => WorkspaceTab::Dashboard,
            Self::Source => WorkspaceTab::Source,
            Self::BuildTest => WorkspaceTab::BuildTest,
            Self::Run => WorkspaceTab::Run,
            Self::Updates => WorkspaceTab::Updates,
            Self::Intelligence => WorkspaceTab::ProjectIntelligence,
            Self::Native => WorkspaceTab::NativeMigration,
            Self::Diagnostics => WorkspaceTab::Diagnostics,
            Self::Artifacts => WorkspaceTab::Artifacts,
            Self::ProjectTools => WorkspaceTab::ProjectTools,
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
    Development,
    Operations,
    Intelligence,
}

impl LayoutPreset {
    pub const ALL: [Self; 4] = [Self::Forge, Self::Development, Self::Operations, Self::Intelligence];

    pub const fn title(self) -> &'static str {
        match self {
            Self::Forge => "Forge",
            Self::Development => "Development",
            Self::Operations => "Operations",
            Self::Intelligence => "Intelligence",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct PersistedShellState {
    pub active_surface: PrimarySurface,
    pub active_project_section: ProjectSection,
    pub project_rail_collapsed: bool,
    pub layout_locked: bool,
    pub compact_health: bool,
    pub preset: LayoutPreset,
}

impl Default for PersistedShellState {
    fn default() -> Self {
        Self {
            active_surface: PrimarySurface::Project,
            active_project_section: ProjectSection::Overview,
            project_rail_collapsed: false,
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
    fn project_context_rail_has_stable_navigation() {
        assert_eq!(ProjectSection::ALL.len(), 10);
        assert_eq!(ProjectSection::Source.tab(), WorkspaceTab::Source);
        assert_eq!(ProjectSection::Updates.tab(), WorkspaceTab::Updates);
        assert_eq!(ProjectSection::ProjectTools.tab(), WorkspaceTab::ProjectTools);
    }

    #[test]
    fn widget_registry_is_semantically_grouped() {
        assert_eq!(WorkspaceTab::OperationQueue.category(), "Operations");
        assert_eq!(WorkspaceTab::ProjectIntelligence.category(), "Project");
        assert_eq!(WorkspaceTab::NativeMigration.category(), "Project");
    }
}
