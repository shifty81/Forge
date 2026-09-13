use std::fmt;

pub const NATIVE_VERSION: &str = "0.5.0-shadow";
pub const NATIVE_BUILD: &str = "FORGE-NATIVE-GUI-WAVE2-0.5.0-F776";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuthorityPhase {
    Donor,
    Shadow,
    DualRead,
    Mirrored,
    Candidate,
    Primary,
    Retired,
}

impl AuthorityPhase {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Donor => "DONOR",
            Self::Shadow => "SHADOW",
            Self::DualRead => "DUAL-READ",
            Self::Mirrored => "MIRRORED",
            Self::Candidate => "CANDIDATE",
            Self::Primary => "PRIMARY",
            Self::Retired => "RETIRED",
        }
    }

    pub const fn takeover_permitted(self) -> bool {
        matches!(self, Self::Primary | Self::Retired)
    }
}

impl fmt::Display for AuthorityPhase {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NativeIdentity {
    pub product: &'static str,
    pub version: &'static str,
    pub build: &'static str,
    pub phase: AuthorityPhase,
    pub python_authority: bool,
}

impl NativeIdentity {
    pub const fn current() -> Self {
        Self {
            product: "Forge",
            version: NATIVE_VERSION,
            build: NATIVE_BUILD,
            phase: AuthorityPhase::Shadow,
            python_authority: true,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shadow_never_claims_takeover() {
        let id = NativeIdentity::current();
        assert_eq!(id.phase, AuthorityPhase::Shadow);
        assert!(id.python_authority);
        assert!(!id.phase.takeover_permitted());
    }
}
