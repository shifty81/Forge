use crate::operations::CancellationToken;
use std::io::{self, BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProcessSpec {
    pub program: String,
    pub args: Vec<String>,
    pub cwd: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProcessResult {
    pub exit_code: i32,
    pub stopped: bool,
    pub stdout: Vec<String>,
    pub stderr: Vec<String>,
}

fn collect_lines<R: io::Read + Send + 'static>(reader: R, target: Arc<Mutex<Vec<String>>>) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        for line in BufReader::new(reader).lines().map_while(Result::ok) {
            if let Ok(mut rows) = target.lock() { rows.push(line); }
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

fn exit_code(status: ExitStatus) -> i32 { status.code().unwrap_or(1) }

pub fn run_streamed(spec: &ProcessSpec, cancellation: &CancellationToken) -> io::Result<ProcessResult> {
    let mut child = Command::new(&spec.program)
        .args(&spec.args).current_dir(&spec.cwd)
        .stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn()?;
    let out = Arc::new(Mutex::new(Vec::new()));
    let err = Arc::new(Mutex::new(Vec::new()));
    let out_thread = child.stdout.take().map(|reader| collect_lines(reader, out.clone()));
    let err_thread = child.stderr.take().map(|reader| collect_lines(reader, err.clone()));
    let mut stopped = false;
    let status = loop {
        if cancellation.requested() {
            stopped = true;
            terminate_tree(&mut child);
        }
        if let Some(status) = child.try_wait()? { break status; }
        thread::sleep(Duration::from_millis(25));
    };
    if let Some(handle) = out_thread { let _ = handle.join(); }
    if let Some(handle) = err_thread { let _ = handle.join(); }
    let stdout = out.lock().map(|rows| rows.clone()).unwrap_or_default();
    let stderr = err.lock().map(|rows| rows.clone()).unwrap_or_default();
    Ok(ProcessResult { exit_code: if stopped { 130 } else { exit_code(status) }, stopped, stdout, stderr })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn spec_is_explicit_and_cwd_bound() {
        let spec = ProcessSpec { program: "tool".into(), args: vec!["--version".into()], cwd: PathBuf::from(".") };
        assert_eq!(spec.program, "tool"); assert_eq!(spec.args.len(), 1);
    }
}
