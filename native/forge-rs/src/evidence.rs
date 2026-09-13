use crate::identity::NativeIdentity;
use crate::parity::{foundation_matrix, takeover_ready};
use std::fs;
use std::io;
use std::path::Path;

fn esc(value: &str) -> String { value.replace('\\', "\\\\").replace('"', "\\\"").replace('\n', "\\n") }

pub fn evidence_json() -> String {
    let id=NativeIdentity::current(); let rows=foundation_matrix();
    let body=rows.iter().map(|r| format!("{{\"capability\":\"{}\",\"state\":\"{}\",\"note\":\"{}\"}}", esc(r.capability), r.state.as_str(), esc(r.note))).collect::<Vec<_>>().join(",");
    format!("{{\"schema\":\"forge.native.evidence.v1\",\"build\":\"{}\",\"phase\":\"{}\",\"pythonAuthority\":{},\"takeoverReady\":{},\"rows\":[{}]}}", id.build, id.phase, id.python_authority, takeover_ready(&rows), body)
}

pub fn write_evidence(path: &Path) -> io::Result<()> {
    if let Some(parent)=path.parent() { fs::create_dir_all(parent)?; }
    let tmp=path.with_extension("tmp"); fs::write(&tmp, evidence_json())?; fs::rename(tmp, path)?; Ok(())
}

#[cfg(test)]
mod tests { use super::*; #[test] fn shadow_evidence_blocks_takeover() { let text=evidence_json(); assert!(text.contains("\"takeoverReady\":false")); assert!(text.contains("forge.native.evidence.v1")); } }
