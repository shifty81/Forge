# Changelog

## 0.4.389-F60R389 — unified GUI shell + command console

- Normalized every top-level ForgePY workspace around one persistent operating shell: workspace rail, global quick actions, active workspace, persistent project console, and permanent health rail.
- Added a project-aware console command line with autocomplete, command list, Tab completion, Ctrl+Space suggestions, history, and governed project command execution.
- Added cyan ForgePY-native console identity while preserving PASS/WARN/FAIL semantic coloring.
- Converted common confirmation/text prompts and certified GREEN commit entry to embedded in-GUI action cards.
- Reduced Project Workspace to its project-operation rail + dynamic command surface because console/status are now app-wide.

## 0.4.379-F60R379 — immutable package/self-update boundary

- Runtime logs, bootstrap traces, artifacts, updates, `.forge`, build output and machine-local settings are no longer distributable patch/package content.
- Adds one canonical `ForgePackagePolicy` shared by manifests, release packaging and patch construction.
- Adds governed `BuildForgePYPatch.py` so future ForgePY patches cannot accidentally capture live logs.
- ForgePY self-update preflights every queued transport before applying any of them.
- Unsafe legacy self-update transports are moved out of the executable queue into lineage instead of blocking later safe updates.
- Patch engine rejects any ForgePY self-update that attempts to mutate runtime/machine-local paths.

## 0.4.378-F60R378 — global patch target authority

- Patch routing now follows the patch, not the currently selected ForgePY project.
- Normal Git unified-diff `.patch` files are live-checked against all registered projects and auto-route only when exactly one project is compatible.
- Manifest-backed patches remain restricted to their declared project identity and build/source preconditions.
- Ambiguous patches fail closed into review; ForgePY never guesses between multiple compatible registered projects.
- Check Downloads and Approve Download are global registered-project operations.
- Manual Select .patch resolves the target before showing confirmation and displays both target and currently selected project.
- Applying a patch to another project does not switch the visible ForgePY workspace.
- Patch Review Apply Now can run the target project's Full Gate without changing the active project.

## 0.4.377-F60R377 — dual .patch transport + modal ownership hotfix

- `.patch` is now a semantic ForgePY patch transport, not an alias for ZIP.
- Manifest-backed `forge.patch.v1` package patches remain supported unchanged.
- Plain Git unified-diff `.patch` files are detected, context-checked with `git apply --check`, cataloged, approved, queued and applied through the same ForgePY patch workflow.
- Check Downloads now gives raw unified diffs the active project as an explicit routing hint; discovery still never auto-applies them.
- Unified diffs create recovery preimages and durable patch receipts.
- Confirmation/text/download-choice modals remain topmost for their entire modal lifetime instead of demoting after 180 ms.

## 0.4.376-F60R376 — project-refresh telemetry crash hotfix

- Fixes the exact Windows startup crash captured by the F60R375 bootstrap logger.
- `projects.refresh` performance metadata is now passed as metadata, not as the numeric threshold argument.
- `ForgePerformance.record()` is hardened so a mapping passed in the third position is treated as metadata instead of raising `float(dict)`.
- Adds regression coverage for the exact `TypeError: float() argument must be a string or a real number, not 'dict'` failure.
- Retains the F60R375 bootstrap trace path so any subsequent startup problem remains observable.

## 0.4.375-F60R375 — earliest-bootstrap diagnostics

- Adds package-local diagnostics before any ForgePY application import.
- Removes ForgeGui from ForgeStandalone module-level imports.
- Adds durable phase markers through GUI creation/mainloop.
- Adds ForgePYDebug.cmd, which always pauses and points to the bootstrap log.
- Does not reintroduce the Tk startup splash.

## 0.4.374-F60R374 — direct-launch rollback

- Removes the temporary pre-GUI Tk startup/self-test window from normal ForgePY launch.
- Normal startup now creates exactly one Tk root: the ForgePY main window.
- Performs only non-visual Vault/first-run directory bootstrap before opening the GUI.
- Restores the preferred VBS launcher to asynchronous hidden launch.
- Keeps VerifyForgePY.cmd as the explicit deep self-test/quick-gate path.
- Leaves ForgeStartup.py available for diagnostics/legacy compatibility but it is no longer part of normal startup.

## 0.4.373-F60R373 — normal-launch / silent-exit hotfix

- Normal ForgePY launch no longer requires a previously active project or folder-picker selection.
- If activeProject is stale, ForgePY uses the most recently opened valid registered project.
- If no usable registry project exists, ForgePY safely boots its own project contract and opens the Projects surface.
- Normal `ForgePY.vbs` now waits invisibly and shows a startup-error dialog on nonzero exit instead of silently disappearing.
- Unhandled Python startup exceptions are logged and surfaced with a visible diagnostic message.
- Explicit `--choose` retains cancel-to-exit semantics.

## 0.4.372-F60R372 — F408–F412 normalization tranche

- F408: normalized GUI/diagnostic/console/verifier launcher semantics and exit-code propagation.
- F409: startup checks honor returned `ok=False`, attempt safe repair, recheck, and block the main GUI when required authority remains failed.
- F410: generated machine-local adapters can become execution authorities for otherwise weak projects without modifying project source.
- F411: scanner activation performs safe metadata probes; `ForgeToolRuntime` is the sole execution authority.
- F412: Artifact Central browsing uses its SQLite index, project refresh telemetry is reachable, and generated-state ignores are normalized.

## 0.4.367-F60R367 — F308–F407 gap-closure tranche

- Adds dynamic Tool Form models, version constraints, output capture and promotion approvals.
- Adds bounded Vault text FTS, ownership scoring and non-mutating watch primitives.
- Adds source conflict/branch/tag services, transactional restore, scheduler/job recovery and notifications.
- Adds standalone EXE/signing/installer/self-update orchestration models with explicit approval gates.
- Adds isolated plugin invocation, migration registry, performance trace, health/availability/compliance/help services.
- Preserves the established GUI appearance and all non-destructive Vault safety rules.

## 0.4.267-F60R267 — F208–F307 runtime integration tranche

- Integrates previously disconnected activity/state/command/job/worker services.
- Adds governed tool runtime, adapter resolution and approved plugin loading.
- Adds Vault intelligence, verified backups, offline release bundles and certification/support services.
- Preserves patch-only automatic movement and F60R67 Windows startup/native safety boundaries.
- Includes cumulative patch notes covering F108 through F307.

## 0.4.167-F60R167 — F108-F207 cumulative architecture/interface tranche

- Implements the next 100 ForgePY passes from F108 through F207 as one cumulative source checkpoint.
- Normalizes Workspace geometry and command taxonomy while preserving the dark/cyan visual identity.
- Adds Vault search/classification/lineage models, typed tooling contracts, governed probes/execution policy, Artifact Central index, unified activity/receipts, project graph, state/debounce/console/pagination performance foundations.
- Adds settings validation, security redaction, plugin/adapter SDKs, command bus, multi-project job queue, disabled-by-default automation, retention/backup/template/diagnostic/provenance/dependency/SBOM/environment/release models.
- Adds standalone Nuitka build recipe and transactional self-update state-machine planning without claiming unperformed Windows binary certification.
- Keeps automatic non-patch movement disabled and preserves F60R67 Python 3.14 tray/startup safety.

## 0.4.67-F60R67 — Startup surface teardown hotfix

- Fixes F60R66 leaving the completed startup/self-test surface packed above the main ForgePY GUI.
- Destroys only the splash widgets, while preserving the shared Tk interpreter for the main application.
- Keeps the Python 3.14 legacy tray safety policy and detached launcher behavior from F60R66.

## 0.4.66-F60R66 — Windows splash handoff + native crash containment

- Fixes F60R65's hidden-splash deadlock: a reused Tk root now quits the splash mainloop after withdraw, then becomes the main GUI root.
- Disables the legacy raw-ctypes Shell_NotifyIcon tray implementation by default on Python 3.14+ after a host-native `__debugbreak` failure was reported.
- Retains an explicit diagnostic opt-in through `FORGEPY_ENABLE_LEGACY_NATIVE_TRAY=1`.
- Makes ForgePY.cmd prefer pythonw/pyw and detach, eliminating the persistent black console from the normal launcher path.
- Keeps native crash diagnostics enabled.

## 0.4.65-F60R65 — Windows native startup stability

- Reuses one Tk interpreter from startup self-test through the main ForgePY window; no destroy/recreate boundary.
- Stages tray, health, configured services and drive census after the main shell completes its first paint.
- Adds persistent `faulthandler` native crash logs under the ForgePY data root.
- Fully types remaining pointer-sensitive tray Win32 calls used by the ctypes message loop.
- Adds an explicit `services.systemTray` switch plus `FORGEPY_DISABLE_TRAY=1` emergency override.
- Does not change ForgePY's visual appearance.

## 0.4.64-F60R64 — Startup splash completion hotfix

- Fixes a startup-screen race where the completion token could be consumed before the minimum display interval elapsed, leaving the splash window open forever even after every startup phase showed PASS.
- Persists the completed state across Tk polling ticks and closes the splash as soon as the minimum display interval has elapsed.
- Ensures the completion token is emitted even if the startup worker exits through an exception path.
- Shows `Ready` after successful startup checks.

## 0.4.63-F60R63 — Non-destructive Vault intake safety

- Automatic Vault/Downloads intake may move only patch transports.
- Ordinary files are catalog/classification material only and remain in place.
- Project activation hygiene no longer moves debug bundles, manual overwrite packages, or other non-patch files.
- Fixes the Downloads watcher/manual picker race by resolving a moved patch through its immutable Vault catalog record.
- Disables the legacy automatic non-patch archival setting by default and removes its normal GUI toggle.

## 0.4.62-F60R62 — F91-F107 application/runtime normalization

- Preserves the established ForgePY look while normalizing Workspace geometry and keeping the right context rail permanently visible.
- Adds persistent workspace splitter state, lazy heavy-tab creation, shared event/worker infrastructure and startup performance plumbing.
- Adds visible startup self-test, first-run D:\Vault initialization, bounded background drive census and conservative repair diagnostics.
- Promotes tool discovery into a functional Tool Registry with capability activation, execution, generated adapters and Toolchain Doctor.

## 0.4.45-F60R45 — Source Control rail layout correction

- Moves Actions to the far-left Source Control rail.
- Keeps Repository as the expanding center pane.
- Moves Branches / Tags to the far-right rail.
- Makes the Actions rail independently vertically scrollable with a persistent scrollbar.
- Preserves branch/tag controls and repository diff behavior.

## 0.4.44-F60R44 — ForgeGit visual source control + GUI performance + universal update operations

- **F71:** Workspace `Commit GREEN` and `Commit + Push GREEN` are universal ForgePY source-control actions for every Git-backed project.
- **F72:** normalized the local source authority to **ForgeGit** while preserving legacy InternalGit repositories/remotes/settings as compatibility input.
- **F73:** added straightforward branch create/switch/merge/rename/delete workflows and recovery branches.
- **F74:** added an IDE-style visual repository folder tree with Git status, filter, stage/unstage/diff/discard operations.
- **F75:** added branch graph plus local/remote/tag browsing and tag-backed restore branches.
- **F76:** added safe file-level source operations; generic discard never deletes untracked files.
- **F77:** expanded named restore points/tags and branch-from-tag workflows.
- **F78:** ForgeGit now supports integrity verification, verified recovery bundle export, explicit maintenance and branch recovery.
- **F79:** added Working Tree / ForgeGit / GitHub authority comparison and clearer primary-source synchronization.
- **F80:** source-control commit/sync operations write durable Artifact Central receipts.
- **F81:** project list refresh is cache-first; expensive provider/catalog work is no longer required for ordinary UI refresh.
- **F82:** Source Control and Vault heavy data are loaded on demand instead of eagerly blocking startup.
- **F83:** live console rendering is bounded and subprocess output is batched.
- **F84:** Vault drive/unclassified views are paginated instead of attempting thousands of Treeview rows at once.
- **F85:** drive-catalog classification counts and offset queries support scalable browsing.
- **F86:** Patch Review supports multi-select routing/archive/ignore and universal ForgePY apply instead of requiring a project-owned patch command.
- **F87:** Artifact Central browsing/search now runs off the Tk UI thread with paged results.
- **F88:** embedded Python/subprocess lanes force UTF-8-safe redirected output, preventing Windows CP1252 diff crashes.
- **F89:** added `Repair / Rebind Source` for folder replacement/recovery and preserved canonical ForgePY self-version context.
- **F90:** completed compatibility/gap audit, fixed ForgeGit health false-warning logic, and added performance telemetry/reporting.

## 0.4.24-F60R24 — Windows-safe transactional patch preimages

- Treats CRLF/LF-only differences as equivalent for known UTF-8 text source/config files.
- Keeps binary preimage verification byte-for-byte strict.
- Treats a file already equal to the target payload as already satisfied rather than failing.
- Makes ForgePY self-update recovery idempotent after emergency repair or partial pre-application.
- Records `already-satisfied` versus `applied` status in patch receipts.
- Never rolls back files the transaction did not modify.

## 0.4.23-F60R23 — Vault catalog schema migration startup hotfix

- Fixes the F60R22 startup crash `sqlite3.OperationalError: no such column: family_hint` when opening an existing F60R17/F60R12 drive catalog.
- Migrates additive SQLite columns before creating indexes that reference them.
- Preserves existing catalog rows; the Vault index remains derived/non-authoritative data.
- Adds a regression test that opens and migrates the exact F60R17 `projects` table shape.
- Adds a defensive additive migration lane for intermediate `entries` schemas.

# ForgePY Changelog

## 0.4.22-F60R22 — F66–F70 stability / intake / Vault catalog rollup

- **F66 — ForgePY self-host/process containment:** ForgePY now uses a dedicated transactional self-update lane instead of routing its own approved update through a project `patch-apply` operation. Embedded operations use Windows no-window process creation so output stays in the ForgePY Project Console. Minimize-to-tray informational notification is emitted only once per process; genuine update notifications remain independent.
- **F67 — Downloads routing / canonical patch naming:** established `ProjectName__YYYYMMDD__Version.patch` as the standard Downloads transport name. The manifest remains authoritative. Added conservative project-identity matching (including unique family forms such as `Cortex` vs `Cortex-main`) and package-created-time staleness classification.
- **F68 — Actionable global Patch Review:** current candidates and review items across projects share one decision surface with Queue, Queue + Apply, Archive Lineage, Ignore, Reveal and Refresh actions. Fresh base mismatches remain reviewable; genuinely old/superseded packages become historical lineage.
- **F69 — Artifact Central browser:** added an in-application searchable Artifact Central browser instead of exposing only a filesystem folder.
- **F70 — Whole-drive Vault catalog v2:** replaced project-only drive discovery with a SQLite-backed catalog of files/directories, project authorities, nested components, classifications, ownership, patch transports, archives, generated/cache data, unknowns and conservative lineage-family hints. Registration excludes ordinary nested components. Successful drive scans are non-blocking and the Vault UI adds Lineage and Unclassified review surfaces. No arbitrary drive content is moved automatically.
- Added regression coverage for self-update authority, hidden embedded consoles, tray notification dedupe, canonical filename parsing, actionable review, and whole-drive ownership/catalog behavior.

## 0.4.17-F60R17 — F61–F65 ForgePY authority / source-control / right-rail rollup

- **F61 — Canonical icon authority:** added the user-selected ForgePY artwork under `assets/branding/ForgePY.png` plus a multi-resolution Windows `ForgePY.ico`; the main Tk window and native Windows tray now use the canonical project icon.
- **F62 — ForgePY module authority:** added canonical `ForgePY*` facades for settings, paths, intake, patching, health, source control, tray and brand identity; active product code now prefers those names while historical Vault/Forge/PCC implementation modules remain compatibility providers.
- **F63 — Internal Git foundation:** added `ForgePYInternalGit.py` with deterministic per-project bare repositories, `forgepy-internal` remote binding, status, ensure, push-snapshot and history operations. GitHub + ForgePY Internal Git are now the primary source-control authorities; Forgejo is optional compatibility hosting.
- **F64 — Source Control workspace:** replaced the top-level Forgejo workspace with Source Control. The workspace exposes Internal Git setup/snapshot/history, GitHub push/sync/configuration, working-tree review and optional Forgejo compatibility controls.
- **F65 — Right-rail project operations:** expanded the existing health rail with compact Patch Intake controls (`Select .patch…`, `Check Downloads`) and project-context status showing version/build, branch, GitHub/Internal Git readiness and root.
- Fresh ForgePY data roots now prefer `ForgePY` naming while still adopting existing `Forge`/`Vault` homes for migration safety.
- Added `docs/NEXT_20_PASSES_F61_F80.md`, `docs/INTERNAL_GIT.md`, and `docs/FORGEPY_MODULE_AUTHORITY.md`.

## 0.4.12-F60R12 — ForgePY root and product identity normalization

- Renamed the distributable top-level folder from `ProjectControlCenter-Standalone` to `ForgePY`.
- Added canonical `ForgePY.vbs`, `ForgePY.cmd`, `ForgePYConsole.cmd`, and `VerifyForgePY.cmd` root surfaces.
- Added `ForgePYVersion.py` and `ForgePYStandalone.py` canonical Python authorities while retaining F60-era import/shortcut compatibility.
- Moved PCC/Vault legacy launchers out of the root into `compat/legacy-launchers/`.
- Moved historical update/source ZIPs to `archive/releases/` and legacy standalone docs to `docs/history/`.
- Renamed package release authority to `FORGEPY_PACKAGE_MANIFEST.json` and project identity to `forgepy`.
- Normalized visible application branding to ForgePY while preserving Vault as a subsystem/workspace and PCC as the project-owned control contract.
- Added preferred `FORGEPY_*` environment aliases where path/intake authority is resolved, without breaking existing `FORGE_*` / `VAULT_*` settings.

## 0.4.11-F60R11 — Manual Patch Selection / Descriptive Transport Recovery

- Added **Updates → Apply Patch…** as an explicit user-authorized file picker for descriptively named `.patch` and `.zip` packages.
- Manual selection verifies archive safety, SHA-256, project identity, package-date evidence, and current build/source preconditions before anything becomes executable.
- A manually selected patch may be promoted from existing Candidate/Lineage evidence without copying it into the project root or renaming it to `incoming.patch`.
- The original selected transport is retained; Forge applies from its immutable Artifact Central/Vault copy.
- Successful manual approval immediately runs the validated patch queue, then normal Full Gate certification can proceed.
- `incoming.patch` remains a compatibility root transport, but descriptive project patches no longer depend on that transitional filename.

## 0.4.10-F60R10 — Explicit Manual Intake Authority

- Separated explicit operator file selection from passive root/Downloads discovery.
- Preserved F60R9's fail-closed rule: passive descriptively named root patches remain Patch Lineage and never auto-queue.
- Added a reusable manual-approval path that re-validates live project/build authority before queue promotion.

# 0.4.9-F60R9 — Queue Authority + Patch Lineage Normalization

- Downloads/global watchers never create executable queue state.
- Added non-executable `CANDIDATE` and `LINEAGE` patch states.
- Only explicit approval or exact project-root `incoming.patch` may create `QUEUED`.
- `incoming.patch` is checked against project identity, package date evidence, build/version/Git/GREEN preconditions, and hash before queueing.
- Arbitrary historical `*Patch*.zip` root files are moved to project Patch Lineage instead of being treated as pending updates.
- Pre-F60R9 QUEUED/STAGED rows without durable approval evidence are automatically demoted to Patch Lineage.
- Canonical Forge patches apply directly from Artifact Central; `updates/inbox` is now legacy-project compatibility only.
- Generic project health no longer counts raw root ZIPs or legacy `updates/inbox` files as pending updates.
- Added `forge.project.v1` contract validation and explicit update-policy declaration.

## 0.4.8-F60R8 — Downloads approval / incoming.patch

- Downloads remains catalog-only but now surfaces compatible update notifications and an explicit **Approve Download…** workflow.
- **Apply Updates** can offer a compatible cataloged Downloads package for explicit approval instead of silently doing nothing when the queue is empty.
- Added **Check Downloads** for an immediate user-requested scan.
- Intake watcher now scans immediately at startup rather than waiting one complete polling interval.
- Added durable download approval evidence (`approved_utc`, `approved_root`) and approval receipts.
- Approved Downloads packages can be staged/applied; unapproved Downloads-origin queues remain fail-closed and are demoted to AVAILABLE.
- Added normalized single-file root transport `incoming.patch` while preserving legacy `.zip` compatibility.
- A manual trusted-root drop of bytes already cataloged from Downloads is treated as explicit approval instead of being rejected as a duplicate.
- `forge.patch.v1` is now a strict modern patch schema alongside the existing Vault v2 compatibility schema.


## 0.4.7-F60R7 — GUI responsiveness / Windows process containment

- eliminates the remaining periodic Windows console flash path from GREEN fingerprint Git probes
- caches governed-source GREEN fingerprints behind a cheap Git work-tree token instead of re-hashing the project every health interval
- increases background health cadence to 30 seconds and pauses health/intake work while foreground jobs run
- makes ordinary project switching use cached registry metadata; full project re-discovery/health is now explicit Rescan work
- prevents overlapping status refresh threads
- time-budgets the Tk event drain and throttles console autoscroll during large compiler logs
- stops updating hidden duplicate log views on every output line
- relaunches Forge directly through Python/pythonw after updates instead of opening Forge.vbs, avoiding Windows Open File Security Warning on restart
- hardens Forge-owned dialogs as transient owned tool windows and replaces simpledialog prompts with Forge-owned modal text prompts
- extends no-window subprocess policy to GREEN/source identity and repository hygiene probes
# Forge 0.4.6-F60R6

- Fixed first-repository bootstrap after a GREEN gate when `.git` exists but `HEAD` is unborn.
- `Initialize / Adopt Git` can bind a declared GitHub authority, fetch remote `main`, and adopt it as parent history without replacing working-tree files.
- Source Review / Full Diff no longer fail with `fatal: ambiguous argument 'HEAD'` on an unborn repository.
- Forge's project contract now declares `https://github.com/shifty81/Forge` as canonical GitHub authority.
- `ForgeSourceControl.py` is now authoritative; `VaultSourceControl.py` is a compatibility shim.
- Every successful Forge-hosted Full Gate records a durable governed-source fingerprint in Artifact Central.
- Generic Git projects now gain protected `Commit GREEN` plus upstream-aware push fallback while project-native source-control commands still win when present.
- Open GitHub and project passports can use declared project metadata before a live remote is configured.

# Forge 0.4.5-F60R5

- Fixed periodic Windows console flashing from active-project health/status scans: Git and provider probes now use no-window execution and health refreshes cannot overlap.
- Fixed Windows cross-volume Artifact Central intake by copy+SHA-256 verify+same-volume atomic promotion rather than C:→D: `os.replace`.
- Added GitHub-native project onboarding: clone a repository into the configured Projects Root, register it, persist its GitHub source URL, open the repository in a browser, and expose normal FF-only pull through Source Control.
- Added scrollable middle command workspaces so Source Control, Tooling, Updates, Diagnostics and Build/Run can grow without clipping the last actions.
- Added a universal registered-project capability matrix and sequential Build All operation; each project keeps its own provider/contract authority and Forge only falls back to build-marker inference when necessary.
- Added command-registry PCC discovery for mature projects that expose `ProjectCommandRegistry.ps1` + `-Command`, including canonical Full Gate and Build aliases. Havenwild therefore uses its existing `HavenwildTools.ps1` command authority instead of Forge inventing a generic Rust Full Gate.
- Hardened streamed project output to UTF-8/replace so Unicode diagnostics cannot crash Forge under a legacy Windows CP1252 host.
- Added F60R5 regression coverage for GitHub normalization, cross-volume promotion, command-registry precedence, hidden periodic probes, Unicode streaming, scrollability, health-scan serialization and universal capabilities.

# Forge 0.4.3-F60R3

- Corrected the Windows x64 system-tray ctypes ABI declarations so pointer-sized LPARAM/LRESULT/HWND values are not truncated by implicit c_int conversion.
- Removed the duplicate compact header health monitor; the collapsible right-side Forge Health gauge is now the single health surface.
- Forge is the application/product authority; Vault remains a workspace and compatibility namespace.
- Forge self-update restart now relaunches Forge.vbs / ForgeStandalone.py and recognizes Forge project IDs as application-root updates.
- F60R3 is cumulative over the F60R2 pending-update isolation repair.

## 0.4.2-F60R2 — Forge authority rename + pending-queue isolation

- Restored **Forge** as the application/product authority; Vault is now a Forge workspace/tab.
- `Forge.cmd`, `Forge.vbs`, `ForgeStandalone.py`, `ForgeGui.py`, `ForgeConsole.py`, `ForgeHealth.py`, `ForgeGate.py` and `ForgeVersion.py` are authoritative entry surfaces.
- `Vault.*` application launchers remain compatibility aliases so existing shortcuts do not break.
- Fixed project-health contamination where legacy `unassigned` intake rows could appear as pending updates on every unrelated project.
- Forge self-hosted gate and package manifest now report one coherent Forge version/build identity.
- Tray, IDE, health rail and application chrome now identify Forge; the Vault tab retains Vault Library / Artifact Central terminology.

# Vault Changelog

## 0.2.0-F11-F20 — 2026-09-09

- Renamed the universal standalone application authority from Forge/PCC to **Vault**.
- Kept Forge and ProjectControlCenter launch/module names as migration shims only.
- Added universal transactional patch mutation and fail-closed rollback.
- Added source self-update/restart-required flow.
- Certified root-drop and Downloads intake paths against the same update transport.
- Expanded Stardew toolkit discovery for `tools/control/StardewModdingKitTools.ps1`.
- Added PowerShell action recovery from ValidateSet, `$Action` switch cases and comparisons.
- Added menu-utility fallback instead of scan-only behavior.
- Added .NET build/Release/full-gate inference.
- Expanded Vault scans with discovery, command/capability and toolchain intelligence.
- Added Tool Commands/Source metrics and Build/Gate/Run capability display.
- Added F11-F20 regression tests while preserving F01-F10 compatibility tests.

## 0.1.0-F01-F10

- Initial standalone Forge extraction from ProjectControlCenter 0.10.2.
- Added project Health, Downloads intake queue, Vault archive, console fallback and project-provider compatibility.

## 0.3.0-F21-F40

- Fixed Full Gate coupling to malformed/duplicate global Downloads patches; only active-root patch rejection is gate-blocking.
- Added unchanged-rejection suppression to stop the watcher from reprinting the same Downloads rejection every cycle.
- Added portable Vault settings, hash-verified Vault Home migration and D:\ defaults.
- Added D: project scanning/indexing with nested project relationships.
- Added project registry portable paths so projects can rebind after a Projects Root drive migration.
- Added hash-verified **Migrate Active Project** workflow into the configured Projects Root; original project remains rollback evidence.
- Added Forgejo application tab with server, doctor, backup, users, Actions token/secret and repository API operations.
- Expanded Vault-owned Git source-control authority for GitHub + local Forgejo remotes.
- Reworked middle workspace command surfaces into separated command-purpose categories.
- Added F21-F40 regression tests for intake isolation, rejection suppression, Vault/project storage migration, D-drive project indexing, portable registry rebinding and Forgejo v16 CLI command shapes.

## 0.4.0-F41-F60 — 2026-09-09

- Reworked the application shell around a collapsible left Vault workspace rail and collapsible right Vault Health gauge.
- Added native Windows system-tray lifecycle with restore/context-menu workflows, Explorer/taskbar restart recovery and tray-specific interface settings.
- Expanded Settings into Services, Storage, Intake & Artifacts, Source Control, IDE, Tooling, Components, Cortex, Security and Interface pages.
- Added a Vault-custom Monaco IDE as an optional **separate pop-out process/window** hosted by pywebview/WebView2, while retaining the native Tk recovery editor.
- Added strict `vault.patch.v2` verification classes, package timestamp evidence, live target build/Git/GREEN binding verification and legacy-review routing.
- Normalized recognized operational artifacts into per-project Artifact Central trees with SHA-256 receipts.
- Expanded project tooling inventory across root launchers, project contracts, tool registries, scripts, Blender and conventional automation trees.
- Added Blender CLI safety adapter using background mode, disabled autoexec and explicit Python exception exit codes.
- Added an open-source optional component registry for Monaco, pywebview, watchfiles, Tree-sitter, ripgrep and psutil.
- Added Cortex as a first-class Vault workspace while preserving its standalone application/service boundary.
- Added 8 F41-F60 regression tests; complete suite now covers 25 tests.

## 0.4.1-F60R1 — Downloads catalog-only safety hotfix

- Downloads/global watched folders no longer auto-queue patch transports.
- Valid downloaded patches are retained as `AVAILABLE` under per-project Artifact Central and are non-executable.
- Invalid/oversized/malformed global patch candidates are moved to per-project or `unassigned` Artifact Central review as inert evidence when safe to archive.
- Full/quick/fast/build/apply project operations no longer poll Downloads.
- Only deliberate active-project root drops auto-enter the executable `QUEUED` state.
- Root-drop intake now explicitly marks the active project root as trusted.
- GUI/manual intake distinguishes queued root patches, available downloads, review transports, ordinary artifacts, and blocking trusted-root errors.
