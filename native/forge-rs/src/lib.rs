//! Forge Native foundation library.
//!
//! The SHADOW phase now includes the real native desktop shell. Python ForgePY
//! remains the operational authority while Rust owns the graphical shell,
//! dock/widget model, foreground queue, console, and progressively more backend
//! services. Takeover remains explicit and parity-gated.

pub mod contracts;
pub mod identity;
pub mod operations;
pub mod parity;
pub mod paths;
pub mod transactions;
pub mod evidence;
pub mod shell;
pub mod journal;
pub mod project;
pub mod settings;
pub mod jobs;
pub mod process_host;
pub mod protocol;
pub mod gui;
pub mod intelligence;
pub mod toolchains;

pub use identity::{AuthorityPhase, NativeIdentity, NATIVE_BUILD, NATIVE_VERSION};
