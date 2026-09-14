# F976 — ShellAnchor / ToolPanel Compile Repair

## Trigger
Windows Rust SHADOW certification reached `cargo check --all-targets` and failed with a cascade of trait errors after F975.

## Root cause
`ShellAnchor` had two adjacent `#[derive(...)]` attributes, while the intended `ToolPanel` derive was separated from `ToolPanel` by the newly inserted shell enums. Rust therefore applied both derives to `ShellAnchor` and none to `ToolPanel`.

## Repair
- Keep one derive on `ShellAnchor`:
  `Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize`.
- Restore the full same derive set directly on `ToolPanel`.
- No shell geometry, panel routing, Cortex placement, provider hierarchy, parity identity, or takeover state changes.
- Add `test_forge_native_f976_shell_anchor_compile_repair.py` so future insertions cannot steal the `ToolPanel` derive.

## Expected collapsed errors
This directly addresses the observed duplicate-implementation errors on `ShellAnchor` and the downstream missing `Copy`, `Clone`, `Debug`, `Hash`, `PartialEq`, `Serialize`, and `Deserialize` bounds on `ToolPanel`. Those missing bounds caused the DockState, registry, PanelIntent, persistence, and ownership/move failures.

## Verification available in producer environment
45/45 cumulative Python structural tests PASS.

Cargo/rustc are not installed in the producer environment, so Windows Rust SHADOW remains the authoritative compile verification.

## Authority
- Certified donor/baseline remains F797.
- Native build identity remains `FORGE-NATIVE-PCC-ASSET-BRIDGE-0.7.0-F797`.
- Phase remains SHADOW.
- `takeoverReady` remains false.
