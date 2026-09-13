use crate::identity::{AuthorityPhase, NativeIdentity};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParityState {
    Pass,
    Missing,
    Different,
    IntentionallySuperseded,
}

impl ParityState {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Pass => "PASS",
            Self::Missing => "MISSING",
            Self::Different => "DIFFERENT",
            Self::IntentionallySuperseded => "INTENTIONALLY_SUPERSEDED",
        }
    }

    pub const fn blocks_takeover(self) -> bool {
        matches!(self, Self::Missing | Self::Different)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ParityRow {
    pub capability: &'static str,
    pub state: ParityState,
    pub note: &'static str,
}

pub fn foundation_matrix() -> Vec<ParityRow> {
    vec![
        ParityRow { capability: "application-identity", state: ParityState::Pass, note: "native identity + authority phase modeled" },
        ParityRow { capability: "project-contract", state: ParityState::Different, note: "bounded contract probe is native; full semantic JSON authority remains Python-owned" },
        ParityRow { capability: "project-branding", state: ParityState::Pass, note: "bounded project icon/name probe modeled" },
        ParityRow { capability: "project-intelligence", state: ParityState::Different, note: "bounded zero-tooling census + marker/language/nested-root inference implemented; project-profile authority pending" },
        ParityRow { capability: "toolchain-intelligence", state: ParityState::Different, note: "native PATH toolchain discovery and safe inferred-operation candidates implemented; execution policy pending" },
        ParityRow { capability: "path-confinement", state: ParityState::Pass, note: "project-relative escape rejection modeled" },
        ParityRow { capability: "event-protocol", state: ParityState::Pass, note: "versioned line-safe native event/request protocol modeled" },
        ParityRow { capability: "operation-envelope", state: ParityState::Pass, note: "queued/running/cancelling/terminal state model present" },
        ParityRow { capability: "single-flight-jobs", state: ParityState::Pass, note: "one-active-job queue and stop semantics modeled" },
        ParityRow { capability: "operation-queue-ui", state: ParityState::Pass, note: "active/pending/last-run queue widget with pending cancellation and duplicate coalescing implemented" },
        ParityRow { capability: "process-tree-host", state: ParityState::Different, note: "streamed subprocess host + Windows taskkill tree cancellation implemented; native direct-command certification pending" },
        ParityRow { capability: "transaction-journal", state: ParityState::Different, note: "filesystem checkpoint/rollback journal implemented; production patch parity pending" },
        ParityRow { capability: "settings-path-authority", state: ParityState::Different, note: "Vault/registry path snapshot modeled; full settings schema migration pending" },
        ParityRow { capability: "stdio-ipc", state: ParityState::Different, note: "request/response stdio server implemented; host bridge certification pending" },
        ParityRow { capability: "parity-evidence", state: ParityState::Pass, note: "atomic native evidence receipt writer implemented" },
        ParityRow { capability: "native-shell-model", state: ParityState::Pass, note: "primary surfaces/project branding shell model is shared by the graphical native host" },
        ParityRow { capability: "dock-widget-system", state: ParityState::Pass, note: "egui_dock tabs/splits/resizing/undocking + semantic widget registry + persistent presets/lock implemented" },
        ParityRow { capability: "foreground-operation-queue", state: ParityState::Different, note: "native single-flight queue streams Python-authority PCC operations; direct inferred-operation execution pending" },
        ParityRow { capability: "catalog-storage", state: ParityState::Missing, note: "SQLite/WAL catalog remains the next backend authority wave" },
        ParityRow { capability: "native-gui", state: ParityState::Different, note: "polished eframe/egui ForgePY shell implemented; visual/runtime parity certification and backend takeover remain pending" },
    ]
}

pub fn takeover_ready(rows: &[ParityRow]) -> bool {
    let id = NativeIdentity::current();
    matches!(id.phase, AuthorityPhase::Primary | AuthorityPhase::Retired)
        && !rows.iter().any(|row| row.state.blocks_takeover())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shadow_foundation_cannot_take_over() {
        let rows = foundation_matrix();
        assert!(!takeover_ready(&rows));
        assert!(rows.iter().any(|row| row.state == ParityState::Missing));
    }

    #[test]
    fn gui_wave_records_intelligence_and_queue_widgets() {
        let rows = foundation_matrix();
        assert!(rows.iter().any(|row| row.capability == "project-intelligence"));
        assert!(rows.iter().any(|row| row.capability == "operation-queue-ui" && row.state == ParityState::Pass));
    }
}
