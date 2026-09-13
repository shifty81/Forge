use crate::paths::ForgePaths;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct JournalEntry { pub relative: PathBuf, pub existed: bool, pub backup: PathBuf }

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileJournal { pub root: PathBuf, pub journal_root: PathBuf, pub entries: Vec<JournalEntry> }

impl FileJournal {
    pub fn checkpoint(root: &Path, journal_root: &Path, relatives: &[PathBuf]) -> io::Result<Self> {
        let paths = ForgePaths::new(root)?;
        fs::create_dir_all(journal_root)?;
        let mut entries = Vec::new();
        for relative in relatives {
            let source = paths.confined(relative)?;
            let backup = journal_root.join(relative);
            let existed = source.is_file();
            if existed {
                if let Some(parent) = backup.parent() { fs::create_dir_all(parent)?; }
                fs::copy(&source, &backup)?;
            }
            entries.push(JournalEntry { relative: relative.clone(), existed, backup });
        }
        Ok(Self { root: paths.project_root, journal_root: journal_root.to_path_buf(), entries })
    }

    pub fn rollback(&self) -> io::Result<()> {
        let paths = ForgePaths::new(&self.root)?;
        for entry in self.entries.iter().rev() {
            let target = paths.confined(&entry.relative)?;
            if entry.existed {
                if let Some(parent) = target.parent() { fs::create_dir_all(parent)?; }
                fs::copy(&entry.backup, &target)?;
            } else if target.exists() { fs::remove_file(&target)?; }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};
    fn scratch() -> PathBuf { let n=SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos(); std::env::temp_dir().join(format!("forge-journal-{n}")) }
    #[test]
    fn checkpoint_restores_file() {
        let root=scratch(); fs::create_dir_all(&root).unwrap(); fs::write(root.join("a.txt"), b"before").unwrap();
        let journal=root.join(".journal"); let row=FileJournal::checkpoint(&root,&journal,&[PathBuf::from("a.txt")]).unwrap();
        fs::write(root.join("a.txt"), b"after").unwrap(); row.rollback().unwrap();
        assert_eq!(fs::read(root.join("a.txt")).unwrap(), b"before"); let _=fs::remove_dir_all(root);
    }
}
