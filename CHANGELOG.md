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
