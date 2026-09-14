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

/// Permanent application-shell anchors. These define stable structural regions
/// around the modular center workspace; they are not detachable workspace tabs.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ShellAnchor {
    TopCommand,
    LeftNavigation,
    RightContext,
    BottomConsole,
    Status,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ContextRailTab {
    Health,
    PatchIntake,
    ProjectContext,
    RecentActivity,
}

impl ContextRailTab {
    pub const ALL: [Self; 4] = [Self::Health, Self::PatchIntake, Self::ProjectContext, Self::RecentActivity];
    pub const fn title(self) -> &'static str {
        match self {
            Self::Health => "HEALTH", Self::PatchIntake => "INTAKE", Self::ProjectContext => "CONTEXT", Self::RecentActivity => "ACTIVITY",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BottomRailTab {
    Console,
    Cortex,
    Operations,
}

impl BottomRailTab {
    pub const ALL: [Self; 3] = [Self::Console, Self::Cortex, Self::Operations];
    pub const fn title(self) -> &'static str {
        match self { Self::Console => "CONSOLE", Self::Cortex => "CORTEX", Self::Operations => "OPERATIONS" }
    }
}

/// Every user-facing Forge surface is represented by a ToolPanel. Structural
/// panels are hosted by permanent rails in the main Forge shell while ordinary
/// workspace tools remain dockable and all panels retain standalone hosting.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ToolPanel {
    ForgeNavigator,
    ProjectNavigator,
    QuickActions,
    Overview,
    Source,
    BuildTest,
    Run,
    Updates,
    Recovery,
    Diagnostics,
    Artifacts,
    ProjectTools,
    ProjectCli,
    ProjectIntelligence,
    NativeMigration,
    AssetDependencies,
    ForgeConsole,
    OperationQueue,
    ProjectHealth,
    PatchIntake,
    ProjectContext,
    RecentActivity,
    Vault,
    Workspace,
    Settings,
    InterfaceManager,
    Status,
}

impl ToolPanel {
    pub const ALL: [Self; 27] = [
        Self::ForgeNavigator,
        Self::ProjectNavigator,
        Self::QuickActions,
        Self::Overview,
        Self::Source,
        Self::BuildTest,
        Self::Run,
        Self::Updates,
        Self::Recovery,
        Self::Diagnostics,
        Self::Artifacts,
        Self::ProjectTools,
        Self::ProjectCli,
        Self::ProjectIntelligence,
        Self::NativeMigration,
        Self::AssetDependencies,
        Self::ForgeConsole,
        Self::OperationQueue,
        Self::ProjectHealth,
        Self::PatchIntake,
        Self::ProjectContext,
        Self::RecentActivity,
        Self::Vault,
        Self::Workspace,
        Self::Settings,
        Self::InterfaceManager,
        Self::Status,
    ];

    pub const fn title(self) -> &'static str {
        match self {
            Self::ForgeNavigator => "Forge Navigator",
            Self::ProjectNavigator => "Project Navigator",
            Self::QuickActions => "Quick Actions",
            Self::Overview => "Overview",
            Self::Source => "Source",
            Self::BuildTest => "Build & Test",
            Self::Run => "Run",
            Self::Updates => "Updates",
            Self::Recovery => "Recovery",
            Self::Diagnostics => "Diagnostics",
            Self::Artifacts => "Artifacts",
            Self::ProjectTools => "Project Tools",
            Self::ProjectCli => "Project CLI",
            Self::ProjectIntelligence => "Intelligence",
            Self::NativeMigration => "Native Migration",
            Self::AssetDependencies => "Asset Dependencies",
            Self::ForgeConsole => "Forge Console",
            Self::OperationQueue => "Operations",
            Self::ProjectHealth => "Project Health",
            Self::PatchIntake => "Patch Intake",
            Self::ProjectContext => "Project Context",
            Self::RecentActivity => "Recent Activity",
            Self::Vault => "Vault",
            Self::Workspace => "Workspace",
            Self::Settings => "Settings",
            Self::InterfaceManager => "Interfaces",
            Self::Status => "Status",
        }
    }

    pub const fn category(self) -> &'static str {
        match self {
            Self::ForgeNavigator | Self::QuickActions | Self::InterfaceManager | Self::Status => "Interface",
            Self::ProjectNavigator
            | Self::Overview
            | Self::Source
            | Self::BuildTest
            | Self::Run
            | Self::Updates
            | Self::Recovery
            | Self::Diagnostics
            | Self::Artifacts
            | Self::ProjectTools
            | Self::ProjectCli
            | Self::ProjectIntelligence
            | Self::NativeMigration
            | Self::AssetDependencies
            | Self::ProjectHealth
            | Self::PatchIntake
            | Self::ProjectContext
            | Self::RecentActivity => "Project",
            Self::ForgeConsole | Self::OperationQueue => "Operations",
            Self::Vault | Self::Workspace => "Workspace",
            Self::Settings => "System",
        }
    }

    pub const fn icon(self) -> &'static str {
        match self {
            Self::ForgeNavigator => "F",
            Self::ProjectNavigator => "P",
            Self::QuickActions => "⚡",
            Self::Overview => "◆",
            Self::Source => "⌘",
            Self::BuildTest => "⚒",
            Self::Run => "▶",
            Self::Updates => "⇣",
            Self::Recovery => "↺",
            Self::Diagnostics => "!",
            Self::Artifacts => "◇",
            Self::ProjectTools => "⋮",
            Self::ProjectCli => ">",
            Self::ProjectIntelligence => "◎",
            Self::NativeMigration => "N",
            Self::AssetDependencies => "A",
            Self::ForgeConsole => ">_",
            Self::OperationQueue => "≡",
            Self::ProjectHealth => "♥",
            Self::PatchIntake => "⇩",
            Self::ProjectContext => "i",
            Self::RecentActivity => "↻",
            Self::Vault => "V",
            Self::Workspace => "W",
            Self::Settings => "S",
            Self::InterfaceManager => "▦",
            Self::Status => "—",
        }
    }

    pub const fn slug(self) -> &'static str {
        match self {
            Self::ForgeNavigator => "forge-navigator",
            Self::ProjectNavigator => "project-navigator",
            Self::QuickActions => "quick-actions",
            Self::Overview => "overview",
            Self::Source => "source",
            Self::BuildTest => "build-test",
            Self::Run => "run",
            Self::Updates => "updates",
            Self::Recovery => "recovery",
            Self::Diagnostics => "diagnostics",
            Self::Artifacts => "artifacts",
            Self::ProjectTools => "project-tools",
            Self::ProjectCli => "project-cli",
            Self::ProjectIntelligence => "intelligence",
            Self::NativeMigration => "native-migration",
            Self::AssetDependencies => "asset-dependencies",
            Self::ForgeConsole => "forge-console",
            Self::OperationQueue => "operations",
            Self::ProjectHealth => "project-health",
            Self::PatchIntake => "patch-intake",
            Self::ProjectContext => "project-context",
            Self::RecentActivity => "recent-activity",
            Self::Vault => "vault",
            Self::Workspace => "workspace",
            Self::Settings => "settings",
            Self::InterfaceManager => "interfaces",
            Self::Status => "status",
        }
    }

    pub fn from_slug(value: &str) -> Option<Self> {
        let normalized = value.trim().to_ascii_lowercase().replace('_', "-");
        Self::ALL.into_iter().find(|panel| panel.slug() == normalized)
    }

    /// Structural panels remain reusable tools, but the normal Forge host routes
    /// them into permanent shell anchors instead of allowing duplicate dock tabs.
    pub const fn shell_anchor(self) -> Option<ShellAnchor> {
        match self {
            Self::QuickActions => Some(ShellAnchor::TopCommand),
            Self::ForgeNavigator | Self::ProjectNavigator => Some(ShellAnchor::LeftNavigation),
            Self::ProjectHealth | Self::PatchIntake | Self::ProjectContext | Self::RecentActivity => Some(ShellAnchor::RightContext),
            Self::ForgeConsole | Self::OperationQueue => Some(ShellAnchor::BottomConsole),
            Self::Status => Some(ShellAnchor::Status),
            _ => None,
        }
    }

    pub const fn is_workspace_tool(self) -> bool { self.shell_anchor().is_none() }

    pub const fn workspace_tab(self) -> Option<WorkspaceTab> {
        match self {
            Self::Overview => Some(WorkspaceTab::Dashboard),
            Self::Source => Some(WorkspaceTab::Source),
            Self::BuildTest => Some(WorkspaceTab::BuildTest),
            Self::Run => Some(WorkspaceTab::Run),
            Self::Updates => Some(WorkspaceTab::Updates),
            Self::Diagnostics => Some(WorkspaceTab::Diagnostics),
            Self::Artifacts => Some(WorkspaceTab::Artifacts),
            Self::ProjectTools => Some(WorkspaceTab::ProjectTools),
            Self::ProjectCli => Some(WorkspaceTab::ProjectCli),
            Self::ProjectIntelligence => Some(WorkspaceTab::ProjectIntelligence),
            Self::NativeMigration => Some(WorkspaceTab::NativeMigration),
            Self::ForgeConsole => Some(WorkspaceTab::ForgeConsole),
            Self::OperationQueue => Some(WorkspaceTab::OperationQueue),
            Self::Vault => Some(WorkspaceTab::Vault),
            Self::Workspace => Some(WorkspaceTab::Workspace),
            Self::Settings => Some(WorkspaceTab::Settings),
            _ => None,
        }
    }
}

/// Compatibility view over the panel-native Project tool family.
///
/// F778-F787 certification and older saved-state readers referred to these
/// destinations as `ProjectSection`. The runtime is ToolPanel-first, but this
/// typed view keeps old contracts readable without restoring a fixed shell.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProjectSection {
    Overview, Source, BuildTest, Run, Updates, Intelligence, Native, Diagnostics, Artifacts, ProjectTools, ProjectCli,
}

impl ProjectSection {
    pub const ALL: [Self; 11] = [
        Self::Overview, Self::Source, Self::BuildTest, Self::Run, Self::Updates,
        Self::Intelligence, Self::Native, Self::Diagnostics, Self::Artifacts, Self::ProjectTools, Self::ProjectCli,
    ];

    pub const fn title(self) -> &'static str {
        match self {
            Self::Overview => "Overview", Self::Source => "Source", Self::BuildTest => "Build & Test",
            Self::Run => "Run", Self::Updates => "Updates", Self::Intelligence => "Intelligence",
            Self::Native => "Native", Self::Diagnostics => "Diagnostics", Self::Artifacts => "Artifacts",
            Self::ProjectTools => "Project Tools", Self::ProjectCli => "Project CLI",
        }
    }

    pub const fn tab(self) -> ToolPanel {
        match self {
            Self::Overview => ToolPanel::Overview, Self::Source => ToolPanel::Source,
            Self::BuildTest => ToolPanel::BuildTest, Self::Run => ToolPanel::Run, Self::Updates => ToolPanel::Updates,
            Self::Intelligence => ToolPanel::ProjectIntelligence, Self::Native => ToolPanel::NativeMigration,
            Self::Diagnostics => ToolPanel::Diagnostics, Self::Artifacts => ToolPanel::Artifacts,
            Self::ProjectTools => ToolPanel::ProjectTools, Self::ProjectCli => ToolPanel::ProjectCli,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LayoutPreset {
    /// Built-in parity preset that mirrors the current certified ForgePY layout.
    Forge,
    Development,
    Operations,
    Intelligence,
    Tooling,
    Minimal,
}

impl LayoutPreset {
    pub const ALL: [Self; 6] = [
        Self::Forge,
        Self::Development,
        Self::Operations,
        Self::Intelligence,
        Self::Tooling,
        Self::Minimal,
    ];

    pub const fn title(self) -> &'static str {
        match self {
            Self::Forge => "ForgePY Mirror",
            Self::Development => "Development",
            Self::Operations => "Operations",
            Self::Intelligence => "Intelligence",
            Self::Tooling => "Tooling / CLI",
            Self::Minimal => "Minimal",
        }
    }

    pub const fn default_locked(self) -> bool { matches!(self, Self::Forge) }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConsoleChannel {
    All,
    Project,
    Forge,
    Build,
    Gate,
    Patch,
    Git,
    Doctor,
}

impl ConsoleChannel {
    pub const ALL: [Self; 8] = [
        Self::All,
        Self::Project,
        Self::Forge,
        Self::Build,
        Self::Gate,
        Self::Patch,
        Self::Git,
        Self::Doctor,
    ];

    pub const fn title(self) -> &'static str {
        match self {
            Self::All => "ALL",
            Self::Project => "PROJECT",
            Self::Forge => "FORGE",
            Self::Build => "BUILD",
            Self::Gate => "GATE",
            Self::Patch => "PATCH",
            Self::Git => "GIT",
            Self::Doctor => "DOCTOR",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct PersistedShellState {
    /// Last selected legacy ProjectSection; maintained as a view over ToolPanel.
    pub active_project_section: ProjectSection,
    /// Project Navigator compact-state compatibility flag.
    pub project_rail_collapsed: bool,
    pub layout_locked: bool,
    pub preset: LayoutPreset,
    pub console_channel: ConsoleChannel,
    pub context_rail_tab: ContextRailTab,
    pub bottom_rail_tab: BottomRailTab,
    pub active_interface_name: String,
}

impl Default for PersistedShellState {
    fn default() -> Self {
        Self {
            active_project_section: ProjectSection::Overview,
            project_rail_collapsed: false,
            layout_locked: LayoutPreset::Forge.default_locked(),
            preset: LayoutPreset::Forge,
            console_channel: ConsoleChannel::All,
            context_rail_tab: ContextRailTab::Health,
            bottom_rail_tab: BottomRailTab::Console,
            active_interface_name: LayoutPreset::Forge.title().to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_forge_surface_is_a_tool_panel() {
        assert_eq!(ToolPanel::ALL.len(), 27);
        assert!(ToolPanel::ALL.contains(&ToolPanel::ForgeConsole));
        assert!(ToolPanel::ALL.contains(&ToolPanel::PatchIntake));
        assert!(ToolPanel::ALL.contains(&ToolPanel::ProjectHealth));
        assert!(ToolPanel::ALL.contains(&ToolPanel::Vault));
        assert!(ToolPanel::ALL.contains(&ToolPanel::Workspace));
    }

    #[test]
    fn mirror_is_default_locked_interface() {
        assert_eq!(LayoutPreset::Forge.title(), "ForgePY Mirror");
        assert!(LayoutPreset::Forge.default_locked());
    }

    #[test]
    fn structural_panels_map_to_permanent_shell_anchors() {
        assert_eq!(ToolPanel::ForgeConsole.shell_anchor(), Some(ShellAnchor::BottomConsole));
        assert_eq!(ToolPanel::PatchIntake.shell_anchor(), Some(ShellAnchor::RightContext));
        assert_eq!(ToolPanel::QuickActions.shell_anchor(), Some(ShellAnchor::TopCommand));
        assert!(ToolPanel::Overview.is_workspace_tool());
    }
}
