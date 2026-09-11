# ForgePY Cumulative Patch Notes — F108 through F407

Cumulative baseline: `0.4.67-F60R67`  
Cumulative target: `0.4.367-F60R367`

## F108–F307 already included

The cumulative patch retains all prior work covering Workspace/interface normalization, permanent right rail, Source Control/ForgeGit/GitHub surfaces, Vault browser/lineage/search foundations, functional Tool Registry/adapters/Toolchain Doctor, Artifact Central/activity/receipts, project families/composite projects, shared workers/state, startup/first-run/repair architecture, plugin/adapter/security/job/release models, runtime-service integration, governed Tool Runtime, verified backups, support/certification services and patch-only automatic movement safety.

## F308–F407 added in this tranche

### Interface/performance architecture
- GUI task registry with overlap protection.
- Shared TTL cache and project snapshot model.
- Workspace metric authority for deterministic default proportions without changing the dark/cyan visual design.

### Tools and adapters
- Dynamic Tool Form view-model generation from typed contracts.
- CLI argument serialization for typed forms.
- Semantic-ish version constraints (`>=`, `<=`, `>`, `<`, `==`, `~`).
- Tool output/artifact capture from declared output patterns.
- Explicit project/family/global promotion approval manager.
- Toolchain provider/install-plan registry covering Git, GitHub CLI, Rust, CMake, Ninja, Node, .NET and Blender; plans never auto-install.

### Vault intelligence
- Bounded text-content FTS service with safe extension allowlist and per-file size cap.
- FTS5 when available with LIKE fallback.
- Project ownership scoring and ambiguity classification.
- Non-mutating file-system snapshot/diff service for future watcher certification.
- Content indexing stays disabled by default.

### Source Control
- Conflict parser and non-automatic resolution plans.
- Branch create/switch and tag helpers.
- Merge preview contract.
- Repository tree cache foundation.

### Backup/recovery
- Backup catalog and manifest inspection.
- Explicit transactional restore lane with verification, staging, rollback copy and zip traversal protection.
- Recovery artifact discovery.

### Automation/jobs
- Minimal scheduler model with global disable gate and >=60-second interval.
- Persisted-job restart normalization to `INTERRUPTED`.
- Notification center with dedupe.
- Headless project command runtime.

### Distribution/release
- Standalone EXE build orchestrator that refuses to run unless the Windows/Nuitka preflight is ready and the operator approves.
- Windows signing plan requiring real operator certificate identity.
- Installer manifest preserving machine data/Vault externally.
- Self-update staging with SHA-256 verification and explicit promotion plan.

### Security/integrity/performance
- Optional isolated subprocess plugin invocation lane.
- Environment allowlist and expanded secret redaction.
- Generic SQLite migration registry.
- Scoped performance trace collector.

### Final integration
- Command availability matrix.
- Adapter compliance audit.
- Health v3 aggregation.
- Documentation/help index.
- New whole-project audit and F60R367 release checkpoint.

## Safety preserved

- Automatic non-patch movement remains forbidden.
- Toolchain installation remains operator-approved.
- Scheduler remains off unless deliberately enabled.
- Restore execution requires explicit approval and retains rollback evidence.
- Windows EXE/signing/tray/self-replacement remain host-certification items.
