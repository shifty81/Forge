use std::fs;
use std::io;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Risk {
    Read,
    Write,
    Destructive,
}

impl Risk {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Read => "read",
            Self::Write => "write",
            Self::Destructive => "destructive",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Capability {
    pub key: String,
    pub label: String,
    pub category: String,
    pub risk: Risk,
    pub mutates: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProjectContractProbe {
    pub path: PathBuf,
    pub exists: bool,
    pub bytes: u64,
    pub schema_marker: bool,
    pub project_id_marker: bool,
    pub full_gate_marker: bool,
}

impl ProjectContractProbe {
    pub fn ready(&self) -> bool {
        self.exists && self.schema_marker && self.project_id_marker && self.full_gate_marker
    }
}

/// Read-only SHADOW-phase contract probe.
///
/// F743 intentionally does not pretend this is a complete JSON authority.  The
/// Python donor remains the semantic parser until the Rust contract crate gains
/// a fully certified parser in the next migration wave.
pub fn probe_project_contract(root: &Path) -> io::Result<ProjectContractProbe> {
    let path = root.join("project.control.json");
    if !path.is_file() {
        return Ok(ProjectContractProbe {
            path,
            exists: false,
            bytes: 0,
            schema_marker: false,
            project_id_marker: false,
            full_gate_marker: false,
        });
    }
    let data = fs::read(&path)?;
    let text = String::from_utf8_lossy(&data);
    let compact: String = text.chars().filter(|c| !c.is_whitespace()).collect();
    Ok(ProjectContractProbe {
        path,
        exists: true,
        bytes: data.len() as u64,
        schema_marker: compact.contains("\"schema\":\"forge.project.v1\""),
        project_id_marker: compact.contains("\"id\":\"forgepy\""),
        full_gate_marker: compact.contains("\"key\":\"gate.full\""),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn scratch() -> PathBuf {
        let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        std::env::temp_dir().join(format!("forge-native-contract-{stamp}"))
    }

    #[test]
    fn missing_contract_is_not_ready() {
        let root = scratch();
        fs::create_dir_all(&root).unwrap();
        let row = probe_project_contract(&root).unwrap();
        assert!(!row.ready());
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn forge_contract_markers_are_recognized() {
        let root = scratch();
        fs::create_dir_all(&root).unwrap();
        fs::write(
            root.join("project.control.json"),
            r#"{"schema":"forge.project.v1","project":{"id":"forgepy"},"commands":[{"key":"gate.full"}]}"#,
        )
        .unwrap();
        let row = probe_project_contract(&root).unwrap();
        assert!(row.ready());
        let _ = fs::remove_dir_all(root);
    }
}
