# Forge Native F911-F950 — Tooling / CLI Workbench

## Goal
Turn the existing modular Forge panels into a usable visual front-end for governed project tooling and CLI operations without introducing a second execution authority or exposing arbitrary shell execution.

## Architecture
F950 keeps the 27-panel registry unchanged. The workbench is composed from existing panels:

- **Project Tools** — searchable command/tool catalog with categories, availability, risk, favorites and command selection.
- **Project CLI** — selected-command detail/form plus safe registered-alias runner.
- **Operations** — active operation, pending queue, cancellation/clear controls and visual command history.
- **Forge Console** — raw transcript/debug output remains a distinct surface.
- **Project Context** — bound project/provider context.
- **Diagnostics** — adjacent validation/debug surface.
- **Quick Actions** — primary actions plus direct `TOOLING` preset activation.

The new built-in `Tooling / CLI` interface preset nests these panels into a command-oriented workspace. It is not new application chrome and can be rearranged/saved like every other interface.

## Registered-command policy
`gui/tooling.rs` defines 18 typed command descriptors. Each descriptor provides a stable ID, visible label, governed alias, category, risk, summary, provider requirement and default-favorite state.

The safe alias runner resolves only registered aliases. Unknown aliases fail closed with a console warning. Arbitrary shell execution remains disabled during SHADOW.

## Queue authority
All executions call `SharedUiState::submit(...)`, which uses the existing project-bound `ForegroundQueue`. The Operations panel reads the same active and pending queue snapshots and exposes stop/cancel/clear controls. No parallel command runner was introduced.

## Internal PCC behavior
Commands that explicitly require the project-owned PCC advertise that requirement and are unavailable when no Internal PCC is detected. Other commands continue through the existing provider hierarchy.

## Reuse
`ToolingUiState` is supplied to both the main docked `ForgePanelViewer` and the standalone Forge tool host. This keeps Project Tools, Project CLI and Operations usable as nested panels or focused standalone tools with the same command model.

## Compatibility
- Existing F798-F910 behavior remains cumulative.
- ForgePY Mirror remains the default locked parity preset.
- ToolPanel registry remains exactly 27 entries for F900 compatibility.
- Legacy F755-F787 GUI certification vocabulary remains intact.
- Native identity remains F797 SHADOW until Windows Cargo/Full Gate certifies promotion.
