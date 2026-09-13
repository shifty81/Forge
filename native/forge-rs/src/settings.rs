use std::env;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SettingsSnapshot {
    pub project_root: PathBuf,
    pub vault_root: PathBuf,
    pub registry_path: PathBuf,
    pub source: &'static str,
}

pub fn snapshot(project_root: &Path) -> SettingsSnapshot {
    let explicit = env::var("VAULT_STORAGE_ROOT").ok().filter(|v| !v.trim().is_empty())
        .or_else(|| env::var("FORGE_VAULT_ROOT").ok().filter(|v| !v.trim().is_empty()));
    let vault_root = explicit.map(PathBuf::from).unwrap_or_else(|| {
        #[cfg(windows)] { PathBuf::from(r"D:\Vault") }
        #[cfg(not(windows))] { project_root.join(".forge").join("vault-shadow") }
    });
    let source = if env::var("VAULT_STORAGE_ROOT").ok().filter(|v| !v.trim().is_empty()).is_some() { "VAULT_STORAGE_ROOT" }
        else if env::var("FORGE_VAULT_ROOT").ok().filter(|v| !v.trim().is_empty()).is_some() { "FORGE_VAULT_ROOT" }
        else { "default" };
    SettingsSnapshot { project_root: project_root.to_path_buf(), registry_path: vault_root.join("project_registry.json"), vault_root, source }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn registry_is_derived_from_vault_root() {
        let root = PathBuf::from("project"); let row = snapshot(&root);
        assert_eq!(row.registry_path.file_name().unwrap(), "project_registry.json");
    }
}
