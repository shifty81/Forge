# ForgePY Cumulative Patch Notes — F108 through F307

This document describes the **cumulative patch from the last Windows runtime checkpoint
F60R67 to F60R267**, including both previously prepared F108–F207 work and the new
F208–F307 integration tranche.

## Baseline

- Starting runtime checkpoint: `0.4.67-F60R67 / FORGEPY-F60R67`
- Cumulative target: `0.4.267-F60R267 / FORGEPY-F60R267`

## F108–F207 already contained in the cumulative patch

### Interface / Workspace
- Workspace geometry normalization.
- Permanent right Health / Patch Intake / Project Context rail.
- Compact/adaptive Quick Actions.
- Universal command categorization.
- Source Control layout and visual repository/branch foundations.
- Vault browser/search/lineage foundations.
- Tool Registry and Toolchain Doctor UI foundations.
- Artifact Central, project-family and composite-project models.
- Lazy/heavy-view, pagination, console-buffer and performance foundations.

### Platform / operations
- Settings/security/plugin/adapter data contracts.
- Universal command bus, jobs, automation profiles and event foundations.
- Retention, backup, templates, diagnostics and provenance models.
- Dependency inventory, SBOM/environment/release models.
- Standalone EXE build recipe and transactional updater state model.
- Clean-PC/portable certification matrix.
- All F60R67 startup/native safety protections retained.

## F208–F307 added in this run

### Runtime integration
- A central `ForgeRuntimeServices` hub now joins events, project state, command bus,
  jobs, workers, activity, provenance and receipts.
- GUI command starts are recorded as runtime operations.
- Shared runtime owns shutdown of worker infrastructure.

### Tools
- Tool Contract v2 with typed coercion and project-confined path validation.
- Governed Tool Runtime with timeout, cancellation, output caps, receipts and activity.
- Visible Tooling execution now routes through the governed runtime.
- Generated adapters gain a registry/resolution service.

### Plugins
- Plugin specs gain explicit approval separate from enabled state.
- Enabled plugins fail closed unless approved.
- A plugin runtime can load approved Python entrypoints and register commands with the
  ForgePY Command Bus.

### Vault / Artifact Central
- Classification facets, ownership/family summaries and duplicate-hash groups.
- Vault search classification/owner facets.
- Artifact Central stale-record cleanup and category summaries.
- Non-destructive Vault safety remains unchanged: classification is not relocation.

### Source control
- Source-authority matrix for Working Tree / HEAD / GREEN / ForgeGit / GitHub.
- Safe branch-name normalizer and divergence states.

### Automation / jobs
- Automation runtime respects the global disabled-by-default gate.
- Conditions and confirmation semantics are explicit.
- Job Queue v2 persists job state and preserves per-project serialization.

### Backup / recovery
- Explicit, operator-invoked verified ZIP backups.
- Per-file SHA-256 backup manifest and verification.
- Restore preview and database backup helpers.
- No automatic restore/delete/move behavior was introduced.

### Release / reproducibility
- Dependency inventory expanded with lockfiles, CMake and .NET presence.
- Offline release-bundle assembly.
- Signing-readiness explicitly refuses to imply a signature exists without operator-owned credentials.

### Performance / support
- Activity history uses a bounded tail read instead of loading the entire ledger.
- Selected tooling background jobs move onto the shared runtime worker service.
- Static certification and redacted support-bundle services added.
- Settings Schema v3 now enforces patch-only automatic intake.
- First-run plan explicitly records no automatic dependency installation and no non-patch movement.

## Still intentionally not claimed as complete

These require the actual Windows host:

1. F60R67/F60R267 Tk lifecycle smoke test.
2. Native `ForgePY.exe` Nuitka one-file build.
3. Defender/SmartScreen certification.
4. Native tray replacement/certification.
5. Real self-replacing EXE update/rollback.
6. Long-duration D: filesystem watcher certification.
7. Visual verification of final Workspace proportions on the user's monitor.
8. Clean-PC dependency-install approval UX.

## Recommended test order at home

1. Test F60R67 first if it has not yet been runtime-certified.
2. If stable, apply the cumulative F60R67 → F60R267 patch.
3. Restart and confirm `0.4.267-F60R267`.
4. Idle 60 seconds.
5. Exercise Projects, Workspace, Vault, Source Control and Tooling.
6. Confirm no non-patch content moved.
7. Activate and run one safe project-specific tool.
8. Run Toolchain Doctor.
9. Run ForgePY Full Gate.
10. Commit + Push GREEN only after runtime smoke remains stable.
