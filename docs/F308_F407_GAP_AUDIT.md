# ForgePY F308–F407 Post-Pass Gap Audit

## Closed or materially improved

- Tool contracts can now drive UI forms, CLI values, version constraints and artifact output capture.
- Tool promotions have an explicit approval manager.
- Toolchain remediation has normalized providers without auto-install behavior.
- Vault gains bounded text-content indexing and non-mutating watcher primitives.
- Source Control gains conflict/branch/tag/merge service primitives.
- Backup restore is no longer planning-only: an explicit approved transaction can stage, restore and roll back.
- Persisted jobs can be marked interrupted after restart; scheduler/notification/headless foundations exist.
- Standalone build, signing, installer and self-update paths are closer to executable orchestration while staying truthful about Windows-host requirements.
- Plugin execution has an isolated subprocess option.
- Generic data migrations and performance tracing now exist.

## Remaining real gaps

1. Windows runtime certification of F60R67/F60R367 is still required before calling startup/native behavior complete.
2. ForgeGui.py remains large; controller extraction is still desirable once Windows stability is proven.
3. Many existing GUI background operations still use direct threads; migration should be guided by real host profiling rather than blind rewrites.
4. Dynamic Tool Form **rendering** in Tk is still not wired; the full form model now exists.
5. Tool version probing needs normalized extraction into `ToolSpec.probe.version` for every adapter/provider.
6. Content FTS indexing needs operator-approved background scheduling and retention controls before enabling by default.
7. Real filesystem watching remains un-certified; the new snapshot/diff model is intentionally polling-safe and non-mutating.
8. Visual three-way conflict resolution is not implemented; conflict detection/plans now exist.
9. Transactional restore needs Windows/project-level smoke certification before being exposed as a one-click normal action.
10. Plugin subprocess isolation is available for `forgepy_invoke` plugins, but legacy Command Bus plugins still run in-process after approval.
11. Scheduler persistence/UI is not enabled by default and has not been long-duration host tested.
12. Nuitka `ForgePY.exe` still must be built on Windows.
13. Authenticode signing still requires operator-owned certificate credentials.
14. EXE self-replacement still needs a real Windows helper/process handoff test.
15. Native tray replacement remains pending.
16. Clean-PC installer/first-run UX still needs visual certification.
17. Vault full-content indexing should gain file-type plug-ins for PDFs/docs only after safe extractors are selected; no OCR is implied.
18. Project-specific adapter compliance should be surfaced in the GUI rather than only via audit data.
19. Performance tracing should be connected to an internal diagnostics panel after measured thresholds are collected.
20. The next pass plan should be driven by actual F60R367 Windows traces rather than another speculative startup rewrite.
