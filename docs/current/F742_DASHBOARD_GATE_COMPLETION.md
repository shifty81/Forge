# ForgePY F742 — Dashboard + Gate Completion Ordering

F742 is a direct repair from the Windows-certified F741 source.

## Repairs

- Resolves the lazy `Dashboard` request to `ForgePY Self` before page construction when ForgePY is the active project.
- Re-activates Dashboard after the Project surface is materialized so the center host cannot remain blank.
- Binds Full Gate completion follow-up to an explicit generation.
- GREEN auto-publication waits until the GUI consumes the `done` event, renders all preceding console output, releases `_busy`, and clears the active process.
- Failed-gate debug generation uses the same post-completion idle boundary.
- Stale success/failure callbacks from an older gate generation are ignored.
- A provider debug command that fails to acquire the operation slot falls back to ForgePY-owned diagnostic evidence.

## Windows acceptance

1. ForgePY selected → Project Dashboard is populated, not blank.
2. Full Gate GREEN reaches `=== END full: PASS ===` before automatic publication starts.
3. No `Another ForgePY job is already running` popup is produced by GREEN publication.
4. Failed gate diagnostics start only after the gate job releases the slot.

## Project-aware quickbar identity

- Project and Workspace quickbars now render the selected project's icon when a project-owned icon can be resolved.
- `project.control.json` may optionally declare `project.icon` or `branding.icon`; ForgePY also checks a bounded set of conventional project icon locations.
- ForgePY resolves `assets/branding/ForgePY.png` automatically. Projects without artwork receive an in-memory initial badge rather than an empty identity slot.
- The quickbar label becomes `<Project> · PROJECT` or `<Project> · WORKSPACE` so the active project remains obvious at a glance.

## Rust successor lane

F742 also establishes the side-by-side `native/forge-rs` successor and ForgePY-owned Rust build/test/run commands. Python ForgePY remains authority until native parity certification. See `docs/current/RUST_MIGRATION.md`.
