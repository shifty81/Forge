use std::fmt;

pub const PROTOCOL_SCHEMA: &str = "forge.native.events.v1";

fn escape_json(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NativeEvent {
    pub sequence: u64,
    pub kind: String,
    pub project_id: String,
    pub operation_id: Option<u64>,
    pub message: String,
}

impl NativeEvent {
    pub fn new(sequence: u64, kind: impl Into<String>, project_id: impl Into<String>, message: impl Into<String>) -> Self {
        Self { sequence, kind: kind.into(), project_id: project_id.into(), operation_id: None, message: message.into() }
    }

    pub fn with_operation(mut self, operation_id: u64) -> Self {
        self.operation_id = Some(operation_id);
        self
    }

    pub fn to_json_line(&self) -> String {
        let op = self.operation_id.map(|value| value.to_string()).unwrap_or_else(|| "null".into());
        format!(
            "{{\"schema\":\"{}\",\"sequence\":{},\"kind\":\"{}\",\"projectId\":\"{}\",\"operationId\":{},\"message\":\"{}\"}}",
            PROTOCOL_SCHEMA,
            self.sequence,
            escape_json(&self.kind),
            escape_json(&self.project_id),
            op,
            escape_json(&self.message),
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NativeRequest {
    Ping,
    Identity,
    Probe,
    Parity,
    ShellModel,
    Shutdown,
    Unknown(String),
}

fn json_string_field(line: &str, key: &str) -> Option<String> {
    let needle = format!("\"{}\"", key);
    let start = line.find(&needle)? + needle.len();
    let tail = &line[start..];
    let colon = tail.find(':')?;
    let value = tail[colon + 1..].trim_start();
    let value = value.strip_prefix('"')?;
    let mut out = String::new();
    let mut escaped = false;
    for ch in value.chars() {
        if escaped {
            out.push(ch);
            escaped = false;
        } else if ch == '\\' {
            escaped = true;
        } else if ch == '"' {
            return Some(out);
        } else {
            out.push(ch);
        }
    }
    None
}

pub fn parse_request_line(line: &str) -> NativeRequest {
    let op = json_string_field(line, "op").unwrap_or_default();
    match op.as_str() {
        "ping" => NativeRequest::Ping,
        "identity" => NativeRequest::Identity,
        "probe" => NativeRequest::Probe,
        "parity" => NativeRequest::Parity,
        "shell-model" => NativeRequest::ShellModel,
        "shutdown" => NativeRequest::Shutdown,
        _ => NativeRequest::Unknown(op),
    }
}

impl fmt::Display for NativeRequest {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Ping => f.write_str("ping"), Self::Identity => f.write_str("identity"),
            Self::Probe => f.write_str("probe"), Self::Parity => f.write_str("parity"),
            Self::ShellModel => f.write_str("shell-model"), Self::Shutdown => f.write_str("shutdown"),
            Self::Unknown(value) => write!(f, "unknown:{value}"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn request_parser_is_fail_closed() {
        assert_eq!(parse_request_line(r#"{"op":"ping"}"#), NativeRequest::Ping);
        assert!(matches!(parse_request_line(r#"{"op":"delete-everything"}"#), NativeRequest::Unknown(_)));
    }

    #[test]
    fn event_is_one_json_line() {
        let line = NativeEvent::new(1, "phase", "forgepy", "hello\nworld").with_operation(7).to_json_line();
        assert!(line.contains(PROTOCOL_SCHEMA));
        assert!(!line.contains('\n'));
        assert!(line.contains("\\n"));
    }
}
