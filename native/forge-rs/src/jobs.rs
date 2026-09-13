use crate::operations::OperationEnvelope;
use std::collections::VecDeque;

#[derive(Debug, Default)]
pub struct SingleFlightJobs {
    next_id: u64,
    active: Option<OperationEnvelope>,
    pending: VecDeque<OperationEnvelope>,
}

impl SingleFlightJobs {
    pub fn submit(&mut self, project_id: impl Into<String>, command: impl Into<String>) -> u64 {
        self.next_id += 1;
        let id = self.next_id;
        self.pending.push_back(OperationEnvelope::queued(id, project_id, command));
        id
    }
    pub fn active(&self) -> Option<&OperationEnvelope> { self.active.as_ref() }
    pub fn pending_len(&self) -> usize { self.pending.len() }
    pub fn start_next(&mut self) -> Option<u64> {
        if self.active.is_some() { return None; }
        let mut job = self.pending.pop_front()?;
        if !job.start() { return None; }
        let id = job.id;
        self.active = Some(job);
        Some(id)
    }
    pub fn cancel_active(&mut self) -> bool { self.active.as_mut().is_some_and(|job| job.request_cancel()) }
    pub fn finish_active(&mut self, ok: bool) -> Option<OperationEnvelope> {
        let mut job = self.active.take()?;
        job.finish(ok);
        Some(job)
    }
    pub fn idle(&self) -> bool { self.active.is_none() }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_one_job_can_be_active() {
        let mut host = SingleFlightJobs::default();
        host.submit("forgepy", "gate.full"); host.submit("forgepy", "test");
        assert!(host.start_next().is_some()); assert!(host.start_next().is_none()); assert_eq!(host.pending_len(), 1);
        let first = host.finish_active(true).unwrap(); assert_eq!(first.state, crate::operations::OperationState::Passed);
        assert!(host.start_next().is_some());
    }
    #[test]
    fn active_cancel_is_stop_semantics() {
        let mut host = SingleFlightJobs::default(); host.submit("forgepy", "build"); host.start_next();
        assert!(host.cancel_active()); let done = host.finish_active(false).unwrap(); assert_eq!(done.state, crate::operations::OperationState::Stopped);
    }
}
