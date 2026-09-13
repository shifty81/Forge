use std::io;
use std::path::{Component, Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ForgePaths {
    pub project_root: PathBuf,
    pub state_dir: PathBuf,
}

impl ForgePaths {
    pub fn new(project_root: impl AsRef<Path>) -> io::Result<Self> {
        let root = project_root.as_ref().canonicalize()?;
        Ok(Self {
            state_dir: root.join(".forge"),
            project_root: root,
        })
    }

    pub fn confined(&self, relative: impl AsRef<Path>) -> io::Result<PathBuf> {
        let relative = relative.as_ref();
        if relative.is_absolute() {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "absolute path is not project-confined"));
        }
        for component in relative.components() {
            if matches!(component, Component::ParentDir | Component::Prefix(_) | Component::RootDir) {
                return Err(io::Error::new(io::ErrorKind::InvalidInput, "path traversal is not allowed"));
            }
        }
        Ok(self.project_root.join(relative))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relative_path_is_confined() {
        let root = std::env::current_dir().unwrap();
        let paths = ForgePaths::new(&root).unwrap();
        let result = paths.confined("app/ForgeGui.py").unwrap();
        assert!(result.starts_with(&paths.project_root));
    }

    #[test]
    fn parent_escape_is_rejected() {
        let root = std::env::current_dir().unwrap();
        let paths = ForgePaths::new(&root).unwrap();
        assert!(paths.confined("../outside").is_err());
    }
}
