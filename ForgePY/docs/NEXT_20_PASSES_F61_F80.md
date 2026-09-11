# ForgePY — F61–F80 Roadmap

This roadmap began at the certified F60R12 baseline. F61–F65 shipped as the F60R17 rollup. Real-world F60R12 testing exposed a ForgePY self-update routing defect, tray-notification spam, a visible child-console path, and weak global Review/Vault behavior, so F66–F70 were deliberately reprioritized to correct those production findings before native drag/drop.

| Pass | Focus | Deliverable | Status |
|---|---|---|---|
| F61 | Canonical ForgePY icon/brand authority | Approved PNG/ICO authority used by GUI and tray | COMPLETE |
| F62 | ForgePY Python/module authority | Canonical `ForgePY*` facades; legacy names compatibility-only | COMPLETE |
| F63 | ForgePY Internal Git foundation | Per-project local bare-repository authority, status/push/history | COMPLETE |
| F64 | Source Control workspace normalization | GitHub + Internal Git primary; Forgejo optional compatibility | COMPLETE |
| F65 | Right-rail project context + patch intake | Compact patch/download controls and project/source context | COMPLETE |
| F66 | Self-host/process containment | Dedicated ForgePY self-update lane, embedded no-window operations, one tray-minimize notice per process | COMPLETE in F60R22 |
| F67 | Downloads routing + age triage | `ProjectName__YYYYMMDD__Version.patch`, project-aware routing, package-created-time staleness, unique alias/family resolution | COMPLETE in F60R22 |
| F68 | Actionable global Patch Review / Lineage | Cross-project candidate/review decisions: queue, apply, archive, ignore, reveal; historical evidence stays lineage | COMPLETE in F60R22 |
| F69 | Artifact Central browser | Searchable in-app per-project artifact/evidence browser | COMPLETE in F60R22 |
| F70 | Whole-drive Vault catalog v2 | Catalog every file/directory plus authorities/components/ownership/classification/lineage hints; non-destructive review UI | COMPLETE in F60R22 |
| F71 | Native Windows drag/drop intake | Real HDROP `.patch`/ZIP/file intake into compact right rail with explicit validation/approval | NEXT |
| F72 | Composite project + duplicate/version lineage graph | Parent workspaces/monorepos, independent child projects, family/version/duplicate relationships and safe organization proposals | PLANNED |
| F73 | Universal adapter v2 | Stronger build/test/run/tool inference for immature PCCs, modding and mixed-language repositories | PLANNED |
| F74 | Toolchain doctor/resolver | Detect SDK/build-tool requirements and offer governed repair/bootstrap actions | PLANNED |
| F75 | Multi-project build/job queue | Queued builds/gates/tests, cancellation and durable receipts | PLANNED |
| F76 | Unified Activity surface | Persistent build/job/Git/update/notification timeline while live console remains visible | PLANNED |
| F77 | Advanced Git workflow | Branch/tag/pull/compare/restore-point operations and remote health | PLANNED |
| F78 | Internal Git recovery/retention | Verification, restore/export, mirror health, pruning and corruption recovery | PLANNED |
| F79 | Windows distribution | Installer/package, canonical icon propagation, shortcuts, repair/uninstall, optional associations | PLANNED |
| F80 | Full release certification | Clean install, update/rollback matrix, watcher soak tests, package audit and takeover-ready certified handoff | PLANNED |
