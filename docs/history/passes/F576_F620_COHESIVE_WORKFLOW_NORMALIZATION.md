# ForgePY F576-F620 — Cohesive Workflow / Duplicate Authority Normalization

This block is cumulative with F450-F575.

## User-facing authority

ForgePY now has one intended operator flow:

`Vault -> Project -> Workspace -> Settings`

- **Vault** owns project discovery/registration/selection, patch intake context, Library/catalog,
  project audit/handoffs, Artifact Central and project source summaries.
- **Project** owns the selected project's Dashboard, Updates, Source Control, Diagnostics,
  Artifacts, Recovery, Build/Test/Run and Full Gate.
- **Workspace** owns native file authoring and the always-present persistent Forge Console.
- **Settings** owns configuration and integration endpoints only.

Historical top-level Operations, Updates, Projects, Source Control, Dashboard, Cortex and IDE
surfaces are compatibility routes, not parallel user-facing products.

## Duplicates removed/contained

- Forge Console and Project CLI are distinct: Forge Console is embedded; Project CLI explicitly opens the project-owned CLI/PCC.
- The compact right-side Patch Intake rail remains the single visible intake authority; duplicate
  quick-bar/picker workflows are removed.
- Apply Updates is no longer repeated on the normal Project Dashboard quick bar; it belongs to
  Project / Updates.
- Source Control no longer has a top-level navigation authority.
- User-facing `Local Source` terminology becomes **ForgeGit**. GitHub remains the remote authority;
  Forgejo remains optional compatibility only.
- Monaco/pywebview install/open controls are removed from the normal Settings/Workspace workflow.
  The native Workspace is authoritative.
- Canonical GUI/CLI/Cortex operation keys are mapped to legacy project-provider strings in one
  Project Protocol table instead of another independent mapping in UnifiedServices.

## Source-tree normalization

Root `app/` is the only code authority. The historical nested `ForgePY/` mirror is classified as
`legacy-mirror`, excluded from package manifests/self-update governed content, and reported by the
Full Gate source-authority check. This avoids two divergent ForgePY products being packaged.

The mirror is not deleted by an overwrite ZIP because deletion cannot be expressed safely by a
plain root overlay. It can be archived/removed later through an explicit source migration once the
live tree proves no external workflow still depends on it.

## Repeated historical failures checked

- Python 3.14 / Win64 ctypes WNDPROC safety — retained from F455.
- missing `re` fallback/debug-bundle error — retained.
- Downloads/root patch watcher moving unrelated files — patch-only intake remains the boundary.
- browser `(1)`/`(12)` duplicate patch names — canonical parser retained.
- patch target guessing — resolve exactly one registered project or fail closed.
- patch selection mutating source — queue only.
- ordinary Build/Fast/Quick/Full Gate consuming queued patches — disabled.
- mixed update authority partial application — preflight whole batch before mutation.
- update recovery — batch checkpoint plus per-patch transactional recovery.
- duplicate project selection/activation discovery — background/cached activation retained.
- Workspace first-open freeze — native lightweight/lazy Workspace retained.
- stale background results crossing projects — generation/root-scoped results retained.
- recursive scanners saturating disk — shared Load Coordinator retained.
- repeated Git subprocess chains / routine GREEN hashing — compact status cache retained.
- duplicate diagnostic/gate execution — canonical Operation Guard added for service/CLI/Cortex path.
- unbounded operation output/history — bounded transcript/tail/job retention retained.
- nested root/ForgePY source duplication — excluded from governed package content and reported.
- root Forge CLI ambiguity — `Forge.cmd` canonical CLI routing retained; no-arg remains GUI compatibility.
- onefile executable conflict — portable Nuitka onedir build remains the target.

## Next executable milestone

After the live local tree applies this overlay and passes Full Gate plus an interactive soak,
ForgePY is ready for the first portable Windows onedir executable candidate. The remaining exe work
is certification and directory-transaction self-update, not another GUI architecture rewrite.

## Additional correctness pass

- Package manifest, self-update policy and GREEN source fingerprint use the same governed-file policy.
- The historical top-level `ForgePY/` mirror is excluded from all three authorities.
- Manifest generation prunes ignored/mirror/build/cache trees before descent.
- Forge Console is the embedded ForgePY console; Project CLI remains a separate explicit project-owned CLI/PCC action.
- The primary app rail no longer hosts certified project-tool category buttons.
- The redundant `Build & Run` Project navigation page is hidden from the normal workflow; the context quick bar owns everyday Build/Run while Advanced retains unusual project-owned variants.
- Heavy background scans never start while an interactive operation is active.
- RuntimeServices exposes `run_canonical()` and the Cortex bridge delegates to it rather than inventing another executor.
- Full Gate has a workflow/source/operation normalization invariant check.
