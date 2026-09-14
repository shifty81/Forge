use super::model::ToolPanel;

pub const PANEL_REGISTRY_VERSION: &str = "FORGE-NATIVE-TOOL-REGISTRY-1.1-F950";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PanelScope {
    Global,
    Project,
    Workspace,
    System,
}

impl PanelScope {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Global => "GLOBAL",
            Self::Project => "PROJECT",
            Self::Workspace => "WORKSPACE",
            Self::System => "SYSTEM",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PanelMaturity {
    Native,
    Hybrid,
    Shadow,
}

impl PanelMaturity {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Native => "NATIVE",
            Self::Hybrid => "HYBRID",
            Self::Shadow => "SHADOW",
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct PanelDescriptor {
    pub panel: ToolPanel,
    pub id: &'static str,
    pub title: &'static str,
    pub category: &'static str,
    pub summary: &'static str,
    pub scope: PanelScope,
    pub maturity: PanelMaturity,
    pub preferred_size: [f32; 2],
    pub minimum_size: [f32; 2],
    pub singleton: bool,
    pub standalone: bool,
}

macro_rules! d {
    ($panel:ident,$summary:expr,$scope:ident,$maturity:ident,$w:expr,$h:expr) => {
        PanelDescriptor {
            panel: ToolPanel::$panel,
            id: ToolPanel::$panel.slug(),
            title: ToolPanel::$panel.title(),
            category: ToolPanel::$panel.category(),
            summary: $summary,
            scope: PanelScope::$scope,
            maturity: PanelMaturity::$maturity,
            preferred_size: [$w, $h],
            minimum_size: [320.0, 220.0],
            singleton: true,
            standalone: true,
        }
    };
}

pub const PANELS: [PanelDescriptor; 27] = [
    d!(ForgeNavigator, "Primary Forge surface navigator and interface entry point.", Global, Native, 360.0, 640.0),
    d!(ProjectNavigator, "Selected-project capability navigator.", Project, Native, 380.0, 700.0),
    d!(QuickActions, "Compact project build, gate, run and refresh command surface.", Project, Hybrid, 760.0, 260.0),
    d!(Overview, "Project status, authority and primary-operation dashboard.", Project, Hybrid, 900.0, 700.0),
    d!(Source, "Repository, ForgeGit and source-control workspace.", Project, Shadow, 980.0, 720.0),
    d!(BuildTest, "Build, test, quality gate and certification operations.", Project, Hybrid, 900.0, 720.0),
    d!(Run, "Governed project launch and runtime surface.", Project, Hybrid, 760.0, 520.0),
    d!(Updates, "Project-aware patch and application update workflow.", Project, Shadow, 960.0, 720.0),
    d!(Recovery, "Repair, debug handoff and source recovery tools.", Project, Hybrid, 860.0, 620.0),
    d!(Diagnostics, "Health, self-test, debug bundle and evidence tools.", Project, Hybrid, 900.0, 700.0),
    d!(Artifacts, "Project outputs, packages, logs and Artifact Central.", Project, Shadow, 900.0, 700.0),
    d!(ProjectTools, "Searchable governed tooling/command catalog plus Internal PCC entry points.", Project, Hybrid, 940.0, 720.0),
    d!(ProjectCli, "Visual registered-command form and safe project CLI alias runner.", Project, Hybrid, 900.0, 640.0),
    d!(ProjectIntelligence, "Bounded project census, toolchains and inferred operations.", Project, Native, 1020.0, 760.0),
    d!(NativeMigration, "Rust parity, certification and takeover evidence.", Project, Native, 980.0, 720.0),
    d!(AssetDependencies, "Missing-asset diagnosis and Vault hydration workflow.", Project, Hybrid, 900.0, 640.0),
    d!(ForgeConsole, "Persistent Forge operation transcript and command composer.", Project, Native, 980.0, 720.0),
    d!(OperationQueue, "Foreground single-flight operation queue and cancellation.", Project, Native, 900.0, 640.0),
    d!(ProjectHealth, "Selected-project health, contract and migration summary.", Project, Native, 440.0, 600.0),
    d!(PatchIntake, "Single governed patch, update and artifact intake surface.", Project, Shadow, 520.0, 620.0),
    d!(ProjectContext, "Bound root, contract, PCC and toolchain context.", Project, Native, 480.0, 560.0),
    d!(RecentActivity, "Recent operation result and queue activity.", Project, Native, 520.0, 540.0),
    d!(Vault, "Project library, catalog, assets and storage authority.", Workspace, Shadow, 1100.0, 760.0),
    d!(Workspace, "Project files and authoring workspace.", Workspace, Shadow, 1180.0, 800.0),
    d!(Settings, "Forge configuration, paths and integrations.", System, Hybrid, 860.0, 700.0),
    d!(InterfaceManager, "Panel library, presets, custom interfaces and layout locking.", Global, Native, 900.0, 700.0),
    d!(Status, "Compact project, operation, interface and version status surface.", Global, Native, 900.0, 260.0),
];

pub fn descriptor(panel: ToolPanel) -> &'static PanelDescriptor {
    PANELS.iter().find(|row| row.panel == panel).expect("every ToolPanel must have a descriptor")
}

pub fn find(query: &str) -> Vec<&'static PanelDescriptor> {
    let q = query.trim().to_ascii_lowercase();
    PANELS.iter().filter(|row| {
        q.is_empty()
            || row.id.contains(&q)
            || row.title.to_ascii_lowercase().contains(&q)
            || row.category.to_ascii_lowercase().contains(&q)
            || row.summary.to_ascii_lowercase().contains(&q)
    }).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn registry_covers_every_panel_with_unique_ids() {
        assert_eq!(PANELS.len(), ToolPanel::ALL.len());
        let ids: HashSet<_> = PANELS.iter().map(|row| row.id).collect();
        assert_eq!(ids.len(), PANELS.len());
        for panel in ToolPanel::ALL { assert_eq!(descriptor(panel).id, panel.slug()); }
    }

    #[test]
    fn every_panel_is_standalone_capable() {
        assert!(PANELS.iter().all(|row| row.standalone));
    }
}
