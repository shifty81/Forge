# ForgePY → Forge Native Rust migration

## Authority rule

ForgePY remains the operational universal project controller until the Rust implementation reaches audited feature parity and passes a dedicated takeover gate. The Rust lane is built, tested, and certified **by ForgePY itself** during migration.

This avoids a flag-day rewrite: all projects can first normalize to the current ForgePY project contract, patch/update protocol, project-local PCC/CLI rules, Vault/Artifact Central layout, and source-control expectations. Rust then replaces implementation layers behind those same contracts.

## Migration lifecycle

`DONOR → SHADOW → DUAL-READ → MIRRORED → CANDIDATE → PRIMARY → RETIRED`

Forge Native is currently **SHADOW**. Python ForgePY is operational authority and recovery authority.

## Migration order

1. **Baseline stabilization — COMPLETE through F742/F753.** Populated Dashboard, correct Full Gate completion ordering, cancellation, project-aware quickbar/icon identity, source authority, clean root/docs, and a governed native lane.
2. **Native contract/core foundation — COMPLETE through F753.** Identity/authority, bounded project/settings probes, path confinement, event/stdio protocol, single-flight jobs, process cancellation, rollback journal, evidence receipts, and the native shell model are governed SHADOW components.
3. **Native storage and catalog.** Project registry/Catalog authority, SQLite/WAL, migrations, backups, settings, durable state and project graph.
4. **Native process/job layer.** Process trees, streaming output, cancellation, operation envelopes, bounded telemetry, durable queues/leases and recovery.
5. **Native Vault/source/update services.** Artifact Central, intake/lineage, diagnostics, ForgeGit/GitHub, transactions, patch apply/rollback, discovery/watchers.
6. **Native shell — ACTIVE through F776.** egui/eframe + egui_dock host now reproduces the ForgePY shell with left navigation, project-aware quickbar/icon, Dashboard, permanent Forge Console, Health rail, status bar, semantic widgets, layout presets/lock, visible operation queue, Workspace/Settings and Project Intelligence.
7. **Cortex integration + installer/updater/security.** Cortex stays behind the application/integration boundary; low-level Forge core remains Cortex-independent.
8. **Parity certification.** Python-vs-Rust fixtures run against the same projects/contracts and each capability is recorded as `PASS`, `MISSING`, `DIFFERENT`, or `INTENTIONALLY_SUPERSEDED`.
9. **Takeover.** Only after repeated GREEN native certification, migration/rollback proof, callers migrated, no active Python dependency, and explicit approval does Forge Native become `PRIMARY`.

## F743 foundation

`native/forge-rs` is now a real dependency-free Rust library/binary foundation rather than a single placeholder. ForgePY owns the status/check/test/build/run/probe/parity/gate workflow through `tools/rust/ForgeRustLane.py`.

The normal Python Full Gate certifies the Rust SHADOW lane whenever Cargo/rustc are available. Toolchain absence remains a visible non-fatal skip while Python ForgePY is production authority; once the toolchain exists, broken governed Rust source is a Full Gate failure.

See [`F743_NATIVE_FOUNDATION.md`](F743_NATIVE_FOUNDATION.md) for the exact slice.

## F744-F753 native wave

The first ten-pass native wave is documented in [`F744_F753_NATIVE_WAVE.md`](F744_F753_NATIVE_WAVE.md). It keeps Python as operational authority while making the Rust successor substantially executable and testable instead of a placeholder.

## F767-F776 native GUI wave 2

The second graphical wave is documented in [`F767_F776_NATIVE_GUI_POLISH_AND_INTELLIGENCE.md`](F767_F776_NATIVE_GUI_POLISH_AND_INTELLIGENCE.md). It prioritizes exact ForgePY shell recreation, polished docking/widget behavior, visible foreground queue semantics, and the first native zero-tooling Project Intelligence/Toolchain Intelligence surfaces.
