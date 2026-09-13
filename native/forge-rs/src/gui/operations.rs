use std::collections::VecDeque;
use std::env;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc};
use std::thread;
use std::time::Instant;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct QueuedOperation {
    pub id: u64,
    pub project_id: String,
    pub label: String,
    pub command: String,
    pub root: PathBuf,
}

#[derive(Debug, Clone)]
pub enum OperationEvent {
    Started { id: u64, label: String },
    Output { id: u64, line: String, stderr: bool },
    Finished { id: u64, label: String, exit_code: i32, stopped: bool },
}

#[derive(Debug)]
struct ActiveOperation {
    row: QueuedOperation,
    cancel: Arc<AtomicBool>,
    started: Instant,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LastRun {
    pub label: String,
    pub state: String,
    pub exit_code: i32,
}

pub struct ForegroundQueue {
    next_id: u64,
    pending: VecDeque<QueuedOperation>,
    active: Option<ActiveOperation>,
    sender: mpsc::Sender<OperationEvent>,
    receiver: mpsc::Receiver<OperationEvent>,
    pub last_run: Option<LastRun>,
}

impl Default for ForegroundQueue {
    fn default() -> Self {
        let (sender, receiver) = mpsc::channel();
        Self { next_id: 0, pending: VecDeque::new(), active: None, sender, receiver, last_run: None }
    }
}

impl ForegroundQueue {
    pub fn active_label(&self) -> Option<&str> { self.active.as_ref().map(|row| row.row.label.as_str()) }
    pub fn active_elapsed_secs(&self) -> Option<u64> { self.active.as_ref().map(|row| row.started.elapsed().as_secs()) }
    pub fn pending_len(&self) -> usize { self.pending.len() }
    pub fn pending(&self) -> impl Iterator<Item = &QueuedOperation> { self.pending.iter() }
    pub fn pending_snapshot(&self) -> Vec<QueuedOperation> { self.pending.iter().cloned().collect() }
    pub fn active_snapshot(&self) -> Option<QueuedOperation> { self.active.as_ref().map(|row| row.row.clone()) }

    pub fn enqueue(&mut self, project_id: impl Into<String>, label: impl Into<String>, command: impl Into<String>, root: PathBuf) -> Option<u64> {
        let project_id = project_id.into();
        let command = command.into();
        if self.active.as_ref().is_some_and(|row| row.row.project_id == project_id && row.row.command == command)
            || self.pending.iter().any(|row| row.project_id == project_id && row.command == command)
        {
            return None;
        }
        self.next_id += 1;
        let id = self.next_id;
        self.pending.push_back(QueuedOperation { id, project_id, label: label.into(), command, root });
        self.start_next_if_idle();
        Some(id)
    }

    pub fn stop_active(&mut self) -> bool {
        if let Some(active) = &self.active {
            active.cancel.store(true, Ordering::SeqCst);
            true
        } else { false }
    }

    pub fn clear_pending(&mut self) { self.pending.clear(); }

    pub fn cancel_pending(&mut self, id: u64) -> bool {
        let before = self.pending.len();
        self.pending.retain(|row| row.id != id);
        self.pending.len() != before
    }

    pub fn poll(&mut self) -> Vec<OperationEvent> {
        let mut rows = Vec::new();
        while let Ok(event) = self.receiver.try_recv() {
            if let OperationEvent::Finished { id, label, exit_code, stopped } = &event {
                if self.active.as_ref().is_some_and(|active| active.row.id == *id) {
                    let state = if *stopped { "STOPPED" } else if *exit_code == 0 { "PASS" } else { "FAIL" };
                    self.last_run = Some(LastRun { label: label.clone(), state: state.into(), exit_code: *exit_code });
                    self.active = None;
                }
            }
            rows.push(event);
        }
        self.start_next_if_idle();
        rows
    }

    fn start_next_if_idle(&mut self) {
        if self.active.is_some() { return; }
        let Some(row) = self.pending.pop_front() else { return; };
        let cancel = Arc::new(AtomicBool::new(false));
        let worker_cancel = cancel.clone();
        let sender = self.sender.clone();
        let worker = row.clone();
        self.active = Some(ActiveOperation { row, cancel, started: Instant::now() });
        thread::spawn(move || run_worker(worker, worker_cancel, sender));
    }
}

fn python_program() -> String {
    env::var("FORGEPY_PYTHON")
        .ok().filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| if cfg!(windows) { "python.exe".into() } else { "python3".into() })
}

fn operation_argv(row: &QueuedOperation) -> (String, Vec<String>) {
    let python = python_program();
    let root = row.root.display().to_string();
    let args = vec![
        row.root.join("app/PCCOperationHost.py").display().to_string(),
        "--root".into(), root.clone(), "--operation".into(), row.command.clone(), "--".into(),
        python.clone(), row.root.join("app/PCCAutoAdapter.py").display().to_string(), row.command.clone(), "--root".into(), root,
    ];
    (python, args)
}

fn reader_thread<R: std::io::Read + Send + 'static>(reader: R, id: u64, stderr: bool, sender: mpsc::Sender<OperationEvent>) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        for line in BufReader::new(reader).lines().map_while(Result::ok) {
            let _ = sender.send(OperationEvent::Output { id, line, stderr });
        }
    })
}

#[cfg(windows)]
fn terminate_tree(child: &mut Child) {
    let pid = child.id().to_string();
    let _ = Command::new("taskkill").args(["/PID", &pid, "/T", "/F"]).stdout(Stdio::null()).stderr(Stdio::null()).status();
    let _ = child.kill();
}

#[cfg(not(windows))]
fn terminate_tree(child: &mut Child) { let _ = child.kill(); }

fn run_worker(row: QueuedOperation, cancel: Arc<AtomicBool>, sender: mpsc::Sender<OperationEvent>) {
    let _ = sender.send(OperationEvent::Started { id: row.id, label: row.label.clone() });
    let (program, args) = operation_argv(&row);
    let mut child = match Command::new(&program)
        .args(&args).current_dir(&row.root).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn()
    {
        Ok(child) => child,
        Err(err) => {
            let _ = sender.send(OperationEvent::Output { id: row.id, line: format!("[FAIL] Could not launch {program}: {err}"), stderr: true });
            let _ = sender.send(OperationEvent::Finished { id: row.id, label: row.label, exit_code: 127, stopped: false });
            return;
        }
    };
    let out = child.stdout.take().map(|reader| reader_thread(reader, row.id, false, sender.clone()));
    let err = child.stderr.take().map(|reader| reader_thread(reader, row.id, true, sender.clone()));
    let mut stopped = false;
    let exit_code = loop {
        if cancel.load(Ordering::SeqCst) && !stopped {
            stopped = true;
            terminate_tree(&mut child);
        }
        match child.try_wait() {
            Ok(Some(status)) => break status.code().unwrap_or(1),
            Ok(None) => thread::sleep(std::time::Duration::from_millis(35)),
            Err(error) => {
                let _ = sender.send(OperationEvent::Output { id: row.id, line: format!("[FAIL] Process host: {error}"), stderr: true });
                break 1;
            }
        }
    };
    if let Some(handle) = out { let _ = handle.join(); }
    if let Some(handle) = err { let _ = handle.join(); }
    let _ = sender.send(OperationEvent::Finished { id: row.id, label: row.label, exit_code: if stopped { 130 } else { exit_code }, stopped });
}

pub fn project_id(root: &Path) -> String {
    root.file_name().and_then(|value| value.to_str()).unwrap_or("project").to_ascii_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn duplicate_foreground_requests_coalesce() {
        let mut queue = ForegroundQueue::default();
        let root = PathBuf::from(".");
        assert!(queue.enqueue("forgepy", "Full Gate", "full", root.clone()).is_some());
        assert!(queue.enqueue("forgepy", "Full Gate", "full", root).is_none());
    }

    #[test]
    fn operation_argv_uses_project_operation_host() {
        let row = QueuedOperation { id: 1, project_id: "forgepy".into(), label: "Build".into(), command: "build".into(), root: PathBuf::from("C:/ForgePY") };
        let (_program, args) = operation_argv(&row);
        assert!(args.iter().any(|value| value.ends_with("PCCOperationHost.py")));
        assert!(args.iter().any(|value| value.ends_with("PCCAutoAdapter.py")));
    }

    #[test]
    fn queued_job_can_be_cancelled_without_touching_active_job() {
        let mut queue = ForegroundQueue::default();
        let root = PathBuf::from(".");
        let _active = queue.enqueue("forgepy", "Build", "build", root.clone()).unwrap();
        let pending = queue.enqueue("forgepy", "Test", "project.self-test", root).unwrap();
        assert!(queue.cancel_pending(pending));
        assert_eq!(queue.pending_len(), 0);
        assert_eq!(queue.active_label(), Some("Build"));
    }
}
