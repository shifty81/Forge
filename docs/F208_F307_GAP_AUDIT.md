# ForgePY F208–F307 Post-Pass Gap Audit

## Materially closed in this tranche

- F108–F207's disconnected service-model problem is reduced by a central runtime service hub.
- Tool execution is now governed by typed validation, timeout/cancel/output policy and receipts.
- Machine-local adapters can now be discovered/resolved instead of only generated.
- Plugins now have a runtime path and explicit approval gate.
- Job state is persistable.
- Vault/Artifact Central have richer intelligence primitives instead of only raw row browsers.
- Explicit verified backup creation exists.
- Offline release bundle creation exists.
- Settings now enforce the patch-only automatic movement invariant.
- Support bundles redact obvious secret-shaped text.
- Activity no longer necessarily reads the complete historical ledger.

## Remaining implementation gaps

1. **Windows runtime certification** remains the highest-priority external blocker.
2. **ForgeGui.py is still large** and should eventually be split by workspace without changing appearance.
3. **Not every direct GUI thread has migrated** to `ForgeRuntimeServices`; the migration is now possible but incomplete.
4. **Plugin sandboxing is process-level policy only**; Python plugins still execute in-process once explicitly approved.
5. **Tool parameter forms are not yet rendered dynamically** in the GUI; contracts are enforced at runtime but the visible form generator remains.
6. **Tool version requirement evaluation** is stored but not yet semantic-version resolved.
7. **Project-family/global tool promotion** exists as policy data but needs a complete visible approval manager.
8. **Vault full-content text indexing/FTS** remains metadata-oriented rather than indexing arbitrary file contents.
9. **Duplicate cleanup remains advisory**; no automatic dedupe/delete is intentionally implemented.
10. **Three-way visual Git conflict resolution** is not implemented.
11. **Backup restore execution** remains deliberately preview-only until a stronger transactional restore lane is certified.
12. **Toolchain installation** remains plan-only and operator-approved.
13. **Automation scheduler** remains disabled; runtime eligibility exists but no unattended scheduler is activated.
14. **Windows code signing** requires real operator certificate/credentials and host tooling.
15. **Nuitka one-file output** still requires a Windows build host.
16. **Self-replacing EXE updater** still needs real host testing.
17. **Filesystem watcher** still needs long-duration host certification.
18. **Release/update channel network transport** remains local/offline model first.
19. **Clean-PC setup wizard** still needs final Windows visual/runtime certification.
20. **Performance work** should continue after host profiling identifies the remaining real UI stalls.

## Recommended next milestone

Do not immediately launch another 100-pass runtime tranche. First certify F60R67/F60R267 on the Windows host, collect startup/performance/native evidence, then plan the next tranche around measured blockers rather than speculative architecture.
