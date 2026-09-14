use std::env;
use std::io;
use std::path::{Path, PathBuf};
use std::process::Command;

use super::model::ToolPanel;

pub const TOOL_HOST_VERSION: &str = "FORGE-NATIVE-TOOL-HOST-1.0-F900";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ToolHostKind {
    Interface,
    Standalone,
}

impl ToolHostKind {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Interface => "DOCKED",
            Self::Standalone => "STANDALONE",
        }
    }
}

pub fn standalone_args(panel: ToolPanel, root: &Path) -> Vec<String> {
    vec![
        "--root".to_string(),
        root.display().to_string(),
        "--tool".to_string(),
        panel.slug().to_string(),
    ]
}

pub fn launch_standalone(panel: ToolPanel, root: &Path) -> io::Result<()> {
    let exe = env::current_exe()?;
    launch_with(&exe, panel, root)
}

pub fn launch_with(executable: &Path, panel: ToolPanel, root: &Path) -> io::Result<()> {
    Command::new(executable)
        .args(standalone_args(panel, root))
        .current_dir(root)
        .spawn()
        .map(|_| ())
}

pub fn sibling_tool_executable(current: &Path) -> PathBuf {
    let file = if cfg!(windows) { "ForgeTool.exe" } else { "ForgeTool" };
    current.parent().unwrap_or_else(|| Path::new(".")).join(file)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standalone_command_is_project_and_panel_bound() {
        let args = standalone_args(ToolPanel::Diagnostics, Path::new("C:/Project"));
        assert_eq!(args[0], "--root");
        assert_eq!(args[2], "--tool");
        assert_eq!(args[3], "diagnostics");
    }
}
