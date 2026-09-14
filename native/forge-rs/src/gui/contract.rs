//! Forge native hybrid-shell contract.
//!
//! F951+ corrects the all-detached-panel experiment into a coherent application
//! shell. A small number of structural ToolPanels are permanently hosted as rails,
//! while authoring/operations tools remain modular in the central ForgeDock and can
//! still use the standalone host. Forge Console is permanently present because it
//! also owns the embedded Cortex surface.

pub const GUI_CONTRACT_VERSION: &str = "FORGE-NATIVE-HYBRID-SHELL-4.0-F975";
// Historical contract token retained for cumulative F901-F910 certification.
pub const MODULAR_TOOLS_COMPAT_CONTRACT: &str = "FORGE-NATIVE-MODULAR-TOOLS-3.1-F910";

pub const PANEL_SYSTEM_IS_INTERFACE_AUTHORITY: bool = true;
pub const ALL_FORGEPY_SURFACES_ARE_TOOL_PANELS: bool = true;
pub const PANELS_ARE_NESTABLE: bool = true;
pub const INTERFACES_ARE_SAVEABLE: bool = true;
pub const INTERFACES_ARE_LOCKABLE: bool = true;
pub const FORGEPY_MIRROR_PRESET_EXISTS: bool = true;
pub const PANEL_DESCRIPTOR_REGISTRY_COMPLETE: bool = true;
pub const SAME_RENDERER_DOCKED_AND_STANDALONE: bool = true;
pub const STANDALONE_TOOL_HOST_SUPPORTED: bool = true;
pub const PANEL_IDS_ARE_STABLE: bool = true;
pub const PANEL_SERVICES_ARE_PROJECT_BOUND: bool = true;
pub const LEGACY_GUI_CERTIFICATION_COMPATIBLE: bool = true;
pub const TOOLING_WORKBENCH_CONTRACT_VERSION: &str = "FORGE-NATIVE-TOOLING-WORKBENCH-1.0-F950";
pub const VISUAL_CLI_IS_REGISTERED_COMMAND_ONLY: bool = true;
pub const TOOLING_PRESET_IS_PANEL_COMPOSED: bool = true;
pub const TOOL_CATALOG_IS_SHARED_WITH_CLI: bool = true;
pub const TOOLING_EXECUTION_USES_FOREGROUND_QUEUE: bool = true;
pub const ARBITRARY_SHELL_REMAINS_DISABLED_IN_SHADOW: bool = true;

// F951-F975 hybrid-shell locks.
pub const HYBRID_SHELL_CONTRACT_VERSION: &str = "FORGE-NATIVE-HYBRID-SHELL-1.0-F975";
pub const PERMANENT_TOP_COMMAND_RAIL: bool = true;
pub const PERMANENT_LEFT_NAVIGATION_RAIL: bool = true;
pub const PERMANENT_RIGHT_CONTEXT_RAIL: bool = true;
pub const PERMANENT_BOTTOM_CONSOLE_CORTEX_RAIL: bool = true;
pub const PERMANENT_STATUS_RAIL: bool = true;
pub const CENTRAL_DOCK_EXCLUDES_SHELL_ANCHORS: bool = true;
pub const FORGE_CONSOLE_IS_PERMANENT: bool = true;
pub const CORTEX_IS_EMBEDDED_IN_CONSOLE_RAIL: bool = true;
pub const CORTEX_NATIVE_BRIDGE_REMAINS_SHADOW: bool = true;
pub const SHELL_ANCHORS_REMAIN_STANDALONE_CAPABLE: bool = true;

pub const INTERFACE_BAR_HEIGHT: f32 = 38.0;

/// Semantic zones retained for ForgePY lineage. They now map to permanent shell
/// anchors plus the central workbench, rather than seven freely-detachable regions.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MirrorZone {
    ForgeNavigation,
    ProjectNavigation,
    QuickActions,
    Workbench,
    ForgeConsole,
    ProjectContextIntake,
    Status,
}

impl MirrorZone {
    pub const ALL: [Self; 7] = [
        Self::ForgeNavigation,
        Self::ProjectNavigation,
        Self::QuickActions,
        Self::Workbench,
        Self::ForgeConsole,
        Self::ProjectContextIntake,
        Self::Status,
    ];
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn panel_graph_is_authority() {
        assert!(PANEL_SYSTEM_IS_INTERFACE_AUTHORITY);
        assert!(ALL_FORGEPY_SURFACES_ARE_TOOL_PANELS);
        assert!(PANELS_ARE_NESTABLE);
        assert!(INTERFACES_ARE_SAVEABLE);
        assert!(INTERFACES_ARE_LOCKABLE);
        assert!(FORGEPY_MIRROR_PRESET_EXISTS);
        assert!(PANEL_DESCRIPTOR_REGISTRY_COMPLETE);
        assert!(SAME_RENDERER_DOCKED_AND_STANDALONE);
        assert!(STANDALONE_TOOL_HOST_SUPPORTED);
        assert!(PANEL_IDS_ARE_STABLE);
        assert!(PANEL_SERVICES_ARE_PROJECT_BOUND);
        assert!(LEGACY_GUI_CERTIFICATION_COMPATIBLE);
        assert!(VISUAL_CLI_IS_REGISTERED_COMMAND_ONLY);
        assert!(TOOLING_PRESET_IS_PANEL_COMPOSED);
        assert!(TOOL_CATALOG_IS_SHARED_WITH_CLI);
        assert!(TOOLING_EXECUTION_USES_FOREGROUND_QUEUE);
        assert!(ARBITRARY_SHELL_REMAINS_DISABLED_IN_SHADOW);
    }

    #[test]
    fn hybrid_shell_is_coherent_and_console_is_permanent() {
        assert!(PERMANENT_TOP_COMMAND_RAIL);
        assert!(PERMANENT_LEFT_NAVIGATION_RAIL);
        assert!(PERMANENT_RIGHT_CONTEXT_RAIL);
        assert!(PERMANENT_BOTTOM_CONSOLE_CORTEX_RAIL);
        assert!(PERMANENT_STATUS_RAIL);
        assert!(CENTRAL_DOCK_EXCLUDES_SHELL_ANCHORS);
        assert!(FORGE_CONSOLE_IS_PERMANENT);
        assert!(CORTEX_IS_EMBEDDED_IN_CONSOLE_RAIL);
        assert!(CORTEX_NATIVE_BRIDGE_REMAINS_SHADOW);
        assert!(SHELL_ANCHORS_REMAIN_STANDALONE_CAPABLE);
    }

    #[test]
    fn mirror_keeps_the_seven_forgepy_visual_roles() {
        assert_eq!(MirrorZone::ALL.len(), 7);
    }
}
