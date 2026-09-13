use std::path::PathBuf;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransactionState {
    Planned,
    Checkpointed,
    Applying,
    Committed,
    RolledBack,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileMutation {
    pub relative_path: PathBuf,
    pub expected_preimage_sha256: Option<String>,
    pub replacement_sha256: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransactionPlan {
    pub id: String,
    pub project_id: String,
    pub state: TransactionState,
    pub mutations: Vec<FileMutation>,
    pub checkpoint_required: bool,
}

impl TransactionPlan {
    pub fn new(id: impl Into<String>, project_id: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            project_id: project_id.into(),
            state: TransactionState::Planned,
            mutations: Vec::new(),
            checkpoint_required: true,
        }
    }

    pub fn add(&mut self, mutation: FileMutation) -> Result<(), &'static str> {
        if self.state != TransactionState::Planned {
            return Err("transaction is no longer mutable");
        }
        if self.mutations.iter().any(|row| row.relative_path == mutation.relative_path) {
            return Err("duplicate transaction target");
        }
        self.mutations.push(mutation);
        Ok(())
    }

    pub fn mark_checkpointed(&mut self) -> Result<(), &'static str> {
        if self.state != TransactionState::Planned {
            return Err("checkpoint requires planned state");
        }
        self.state = TransactionState::Checkpointed;
        Ok(())
    }

    pub fn begin_apply(&mut self) -> Result<(), &'static str> {
        if self.checkpoint_required && self.state != TransactionState::Checkpointed {
            return Err("checkpoint is required before apply");
        }
        if !self.checkpoint_required && self.state != TransactionState::Planned {
            return Err("unexpected transaction state");
        }
        self.state = TransactionState::Applying;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checkpoint_is_required_before_apply() {
        let mut tx = TransactionPlan::new("tx-1", "forgepy");
        assert!(tx.begin_apply().is_err());
        tx.mark_checkpointed().unwrap();
        assert!(tx.begin_apply().is_ok());
        assert_eq!(tx.state, TransactionState::Applying);
    }

    #[test]
    fn duplicate_target_fails_closed() {
        let mut tx = TransactionPlan::new("tx-2", "forgepy");
        let row = FileMutation {
            relative_path: PathBuf::from("app/ForgeGui.py"),
            expected_preimage_sha256: Some("abc".into()),
            replacement_sha256: Some("def".into()),
        };
        tx.add(row.clone()).unwrap();
        assert!(tx.add(row).is_err());
    }
}
