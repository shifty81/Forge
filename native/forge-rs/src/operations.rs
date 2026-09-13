use std::fmt;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OperationState {
    Queued,
    Running,
    Cancelling,
    Passed,
    Failed,
    Stopped,
}

impl OperationState {
    pub const fn terminal(self) -> bool {
        matches!(self, Self::Passed | Self::Failed | Self::Stopped)
    }
}

impl fmt::Display for OperationState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let value = match self {
            Self::Queued => "QUEUED",
            Self::Running => "RUNNING",
            Self::Cancelling => "CANCELLING",
            Self::Passed => "PASS",
            Self::Failed => "FAIL",
            Self::Stopped => "STOPPED",
        };
        f.write_str(value)
    }
}

#[derive(Debug, Clone)]
pub struct CancellationToken {
    requested: Arc<AtomicBool>,
}

impl CancellationToken {
    pub fn new() -> Self {
        Self { requested: Arc::new(AtomicBool::new(false)) }
    }

    pub fn request(&self) {
        self.requested.store(true, Ordering::SeqCst);
    }

    pub fn requested(&self) -> bool {
        self.requested.load(Ordering::SeqCst)
    }
}

impl Default for CancellationToken {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone)]
pub struct OperationEnvelope {
    pub id: u64,
    pub project_id: String,
    pub command: String,
    pub state: OperationState,
    pub started: Option<Instant>,
    pub finished: Option<Instant>,
    pub cancellation: CancellationToken,
}

impl OperationEnvelope {
    pub fn queued(id: u64, project_id: impl Into<String>, command: impl Into<String>) -> Self {
        Self {
            id,
            project_id: project_id.into(),
            command: command.into(),
            state: OperationState::Queued,
            started: None,
            finished: None,
            cancellation: CancellationToken::new(),
        }
    }

    pub fn start(&mut self) -> bool {
        if self.state != OperationState::Queued {
            return false;
        }
        self.state = OperationState::Running;
        self.started = Some(Instant::now());
        true
    }

    pub fn request_cancel(&mut self) -> bool {
        if self.state.terminal() {
            return false;
        }
        self.cancellation.request();
        self.state = OperationState::Cancelling;
        true
    }

    pub fn finish(&mut self, ok: bool) {
        self.state = if self.cancellation.requested() {
            OperationState::Stopped
        } else if ok {
            OperationState::Passed
        } else {
            OperationState::Failed
        };
        self.finished = Some(Instant::now());
    }

    pub fn elapsed(&self) -> Option<Duration> {
        self.started.map(|start| self.finished.unwrap_or_else(Instant::now).duration_since(start))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cancellation_finishes_as_stopped() {
        let mut op = OperationEnvelope::queued(1, "forgepy", "gate.full");
        assert!(op.start());
        assert!(op.request_cancel());
        op.finish(false);
        assert_eq!(op.state, OperationState::Stopped);
    }

    #[test]
    fn passed_operation_is_terminal() {
        let mut op = OperationEnvelope::queued(2, "forgepy", "test");
        op.start();
        op.finish(true);
        assert_eq!(op.state, OperationState::Passed);
        assert!(!op.request_cancel());
    }
}
