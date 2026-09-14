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
        ParityRow { capability: "native-shell-model", state: ParityState::Pass, note: "hybrid native shell: permanent command/navigation/context/Console-Cortex/status anchors surround a modular central workspace" },
        ParityRow { capability: "panel-interface-system", state: ParityState::Pass, note: "ToolPanel registry owns Forge surfaces; structural tools map to permanent shell anchors while workspace tools tab/split/nest/reopen in the central graph" },
        ParityRow { capability: "hybrid-shell-rails", state: ParityState::Pass, note: "permanent top command, left navigation, right context, bottom Console/Cortex and status rails anchor the application around the central ForgeDock" },
        ParityRow { capability: "modular-tool-host", state: ParityState::Pass, note: "all ToolPanels have stable descriptors and share one renderer across nested ForgeDock interfaces and standalone --tool hosts" },
        ParityRow { capability: "forgepy-mirror-preset", state: ParityState::Pass, note: "ForgePY Mirror composes central workspace tools inside permanent structural rails; reusable ToolPanels remain the implementation units" },
        ParityRow { capability: "forge-console-panel", state: ParityState::Pass, note: "Forge Console is permanently hosted in the bottom Console/Cortex rail while retaining the reusable ToolPanel/standalone implementation" },
        ParityRow { capability: "project-context-intake-panels", state: ParityState::Different, note: "Project Health, Patch Intake, Project Context and Recent Activity share the permanent right Context rail; governed intake classification backend remains Python-authority" },
        ParityRow { capability: "project-context-navigation", state: ParityState::Pass, note: "Forge and Project navigation are permanently hosted in the left rail and focus modular central tools" },
        ParityRow { capability: "dock-widget-system", state: ParityState::Pass, note: "ForgeDock owns the central workspace graph; shell anchors are excluded while workspace tools retain nested splits/tabs, focus/reopen, presets and saved layouts" },
        ParityRow { capability: "internal-pcc-bridge", state: ParityState::Different, note: "native Project Tools launches/queues through Python-authority normalized internal PCC bridge; native contract execution pending" },
        ParityRow { capability: "asset-dependency-resolution", state: ParityState::Different, note: "hash-bound Vault/backup hydration is Python-authority and exposed through native Project Tools; native catalog authority pending" },
        ParityRow { capability: "foreground-operation-queue", state: ParityState::Different, note: "native single-flight queue streams Python-authority PCC operations; direct inferred-operation execution pending" },
        ParityRow { capability: "legacy-gui-certification-compatibility", state: ParityState::Pass, note: "F755-F787 GUI probes map to typed ToolPanel compatibility views and stable panel IDs without restoring fixed shell chrome" },
        ParityRow { capability: "visual-cli-workbench", state: ParityState::Pass, note: "F950 Tooling / CLI preset composes Project Tools, Project CLI, Operations, Console, Context and Diagnostics over one allowlisted command catalog and shared project-bound foreground queue" },
        ParityRow { capability: "native-self-update", state: ParityState::Different, note: "native install-mode detection and Windows directory-swap promotion are modeled; bundle build/hash verification and staging use the guarded Python SHADOW bridge until Rust archive authority is certified" },
        ParityRow { capability: "catalog-storage", state: ParityState::Missing, note: "SQLite/WAL catalog remains the next backend authority wave" },
        ParityRow { capability: "native-gui", state: ParityState::Different, note: "hybrid-shell GUI, permanent Console/Cortex rail, modular central workspace, shared tool chrome and standalone host are implemented; Windows runtime certification and backend takeover remain pending" },
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

    #[test]
    fn native_self_update_remains_shadow_gated() {
        let rows = foundation_matrix();
        assert!(rows.iter().any(|row| row.capability == "native-self-update" && row.state == ParityState::Different));
        assert!(rows.iter().any(|row| row.capability == "legacy-gui-certification-compatibility" && row.state == ParityState::Pass));
        assert!(!takeover_ready(&rows));
    }
}
