use std::env;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ToolchainProbe {
    pub key: &'static str,
    pub label: &'static str,
    pub program: &'static str,
    pub path: Option<PathBuf>,
}

impl ToolchainProbe {
    pub fn ready(&self) -> bool { self.path.is_some() }
}

fn executable_candidates(program: &str) -> Vec<String> {
    if cfg!(windows) {
        vec![program.to_string(), format!("{program}.exe"), format!("{program}.cmd"), format!("{program}.bat")]
    } else {
        vec![program.to_string()]
    }
}

pub fn find_program(program: &str) -> Option<PathBuf> {
    let raw = env::var_os("PATH")?;
    for dir in env::split_paths(&raw) {
        for candidate in executable_candidates(program) {
            let path = dir.join(candidate);
            if path.is_file() { return Some(path); }
        }
    }
    None
}

pub fn probe_all() -> Vec<ToolchainProbe> {
    [
        ("git", "Git", "git"),
        ("cargo", "Rust Cargo", "cargo"),
        ("rustc", "Rust Compiler", "rustc"),
        ("python", "Python", if cfg!(windows) { "python" } else { "python3" }),
        ("cmake", "CMake", "cmake"),
        ("ninja", "Ninja", "ninja"),
        ("msbuild", "MSBuild", "msbuild"),
        ("dotnet", ".NET", "dotnet"),
        ("node", "Node.js", "node"),
        ("npm", "npm", "npm"),
        ("java", "Java", "java"),
        ("gradle", "Gradle", "gradle"),
        ("mvn", "Maven", "mvn"),
        ("godot", "Godot", "godot"),
    ]
    .into_iter()
    .map(|(key, label, program)| ToolchainProbe { key, label, program, path: find_program(program) })
    .collect()
}

pub fn ready_count(rows: &[ToolchainProbe]) -> usize { rows.iter().filter(|row| row.ready()).count() }

pub fn program_is_project_local(program: &str, root: &Path) -> Option<PathBuf> {
    let names = if cfg!(windows) {
        vec![program.to_string(), format!("{program}.cmd"), format!("{program}.bat"), format!("{program}.exe")]
    } else {
        vec![program.to_string()]
    };
    names.into_iter().map(|name| root.join(name)).find(|path| path.is_file())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn toolchain_registry_contains_major_forge_ecosystems() {
        let rows = probe_all();
        for key in ["git", "cargo", "python", "cmake", "dotnet", "node", "java"] {
            assert!(rows.iter().any(|row| row.key == key));
        }
    }

    #[test]
    fn executable_candidates_are_bounded() {
        let rows = executable_candidates("cargo");
        assert!(!rows.is_empty());
        assert!(rows.len() <= 4);
    }
}
