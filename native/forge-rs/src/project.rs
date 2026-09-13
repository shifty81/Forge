use crate::contracts::probe_project_contract;
use std::io;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProjectSnapshot {
    pub root: PathBuf,
    pub name: String,
    pub contract_ready: bool,
    pub icon: Option<PathBuf>,
}

fn icon_candidates(root: &Path) -> [PathBuf; 7] {
    [
        root.join("assets/branding/ForgePY.png"), root.join("assets/branding/icon.png"),
        root.join("assets/branding/icon.ico"), root.join("assets/icon.png"), root.join("assets/icon.ico"),
        root.join("src-tauri/icons/icon.png"), root.join("src-tauri/icons/icon.ico"),
    ]
}

pub fn probe_project(root: &Path) -> io::Result<ProjectSnapshot> {
    let contract = probe_project_contract(root)?;
    let icon = icon_candidates(root).into_iter().find(|path| path.is_file());
    Ok(ProjectSnapshot {
        root: root.to_path_buf(), name: root.file_name().and_then(|v| v.to_str()).unwrap_or("Project").to_string(),
        contract_ready: contract.ready(), icon,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn icon_probe_is_bounded_to_known_locations() {
        let rows = icon_candidates(Path::new("root")); assert_eq!(rows.len(), 7);
        assert!(rows.iter().all(|row| row.starts_with("root")));
    }
}
