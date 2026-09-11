# ForgePY F71–F90 Gap Audit

## Gaps found and closed in this tranche

1. **Workspace Commit + Push GREEN depended on project PCC commands.** Closed: ForgePY now owns universal GREEN commit/push operations.
2. **Internal Git naming was split across UI/settings/modules.** Closed: ForgeGit is canonical; legacy names are migration/compatibility only.
3. **Source Control lacked straightforward branch/file workflows.** Closed with branch manager, visual file tree, tags, graph, staging and recovery.
4. **ForgeGit was only a snapshot target.** Closed with integrity verification, portable bundles, recovery branches, maintenance and authority comparison.
5. **Windows Unicode source diff could crash under CP1252.** Closed with UTF-8 stdio/environment normalization.
6. **Patch Review could strand project updates or require a project-native patch command.** Closed: routing is explicit and canonical patches apply through ForgePY's universal transactional engine.
7. **Patch Review had weak operator choices.** Closed: multi-select route/archive/ignore plus queue/apply/reveal.
8. **Vault drive views could create thousands of Tk rows.** Closed with paginated drive/unclassified views and count APIs.
9. **Artifact Central scan/search blocked the GUI.** Closed with threaded/paged browse results.
10. **Project refresh repeated expensive discovery.** Closed for routine refresh; explicit Rescan remains the deep path.
11. **Console growth/redraw contributed to lag.** Closed with a bounded live buffer and batched subprocess output.
12. **ForgePY folder overwrite could lose Git bindings and make the install appear new.** Closed with Repair/Rebind Source and ForgeGit legacy/adoption paths.
13. **ForgeGit health could falsely warn even when the compatibility key was true.** Closed.
14. **Right-rail ForgePY version could lag behind application authority.** Closed by using canonical `ForgePYVersion` for the self-project.

## Remaining audited gaps — intentionally queued after F90

These are real gaps discovered in the existing implementation and should be the next tranche rather than being hidden behind a GREEN gate:

- **Native Windows drag/drop intake:** the right rail still uses file selection; true Explorer drop handling is not yet a certified built-in implementation.
- **Incremental D:\ watcher:** Settings still marks the drive watcher as reserved; catalog updates currently depend on explicit scans/intake polling rather than a certified filesystem-change journal.
- **Visual conflict resolver:** merge conflicts are visible through Git state/diffs, but there is not yet a purpose-built three-way conflict editor.
- **Artifact Central persistent index:** the browser is now responsive, but Artifact Central still walks its file hierarchy in a background worker rather than maintaining its own searchable SQLite/FTS catalog.
- **Release installer/signing:** clean ZIP recovery is verified, but a signed Windows installer, repair/uninstall registration, and Authenticode release pipeline remain outstanding.
- **ForgeGit remote branch publish controls:** branch push/recovery is available, but per-branch publish/upstream tracking can be made more visual.
- **Drive-wide ownership decisions:** Vault detects unclassified/lineage candidates but still needs operator-approved move/link/dedupe plans before it can safely reorganize arbitrary D: content.

No project source should be moved/deleted automatically merely to close these gaps.
