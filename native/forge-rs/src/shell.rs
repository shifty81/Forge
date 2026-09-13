use crate::identity::NativeIdentity;
use crate::project::ProjectSnapshot;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ShellSurface { pub key: &'static str, pub label: &'static str }

pub const PRIMARY_SURFACES: [ShellSurface; 4] = [
    ShellSurface { key: "vault", label: "Vault" }, ShellSurface { key: "project", label: "Project" },
    ShellSurface { key: "workspace", label: "Workspace" }, ShellSurface { key: "settings", label: "Settings" },
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ShellModel { pub build: &'static str, pub phase: &'static str, pub project_name: String, pub project_icon: String }

impl ShellModel {
    pub fn from_project(project: &ProjectSnapshot) -> Self {
        let identity=NativeIdentity::current();
        Self { build: identity.build, phase: identity.phase.as_str(), project_name: project.name.clone(), project_icon: project.icon.as_ref().map(|p| p.display().to_string()).unwrap_or_default() }
    }
    pub fn to_json(&self) -> String {
        format!("{{\"build\":\"{}\",\"phase\":\"{}\",\"projectName\":\"{}\",\"projectIcon\":\"{}\",\"surfaces\":[\"Vault\",\"Project\",\"Workspace\",\"Settings\"]}}", self.build, self.phase, self.project_name.replace('"', "\\\""), self.project_icon.replace('\\', "\\\\").replace('"', "\\\""))
    }
}

#[cfg(test)]
mod tests { use super::*; #[test] fn shell_surface_contract_matches_python() { assert_eq!(PRIMARY_SURFACES.map(|v| v.label), ["Vault","Project","Workspace","Settings"]); } }
