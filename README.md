# Forge

Current certified development build: **0.4.8-F60R8**. — Universal Project Control Center

**Product authority:** Forge is the standalone universal Project Control Center and Cortex operations brain. **Vault is a first-class Forge workspace/tab** for catalog, Artifact Central, patch intake, baselines, recovery and storage intelligence. Legacy `Vault.*` launchers/modules remain compatibility aliases during migration.

Forge is project-neutral. A registered project keeps its own project-local PCC, command registry and build scripts as the highest authority. Forge discovers and invokes those capabilities, then uses universal build-marker adapters only when a stronger project-owned operation does not exist.

## Update intake

Downloads is a catalog/review surface, not execution authority. Forge detects compatible downloaded patch packages, archives them under the project's Artifact Central area, and exposes **Updates > Approve Download…** for explicit approval. `Apply Updates` can offer a compatible downloaded package when no update is already queued.

For a deliberate root-drop workflow, use the normalized single reserved transport name **`incoming.patch`**. It is a ZIP-compatible Forge patch container with a top-level `PATCH_MANIFEST.json`; Forge verifies its hash, package date, project identity, and declared build/source preconditions before transactional application. Legacy root patch ZIPs remain supported during migration.

## F60R5 project onboarding and universal tooling

Projects can be registered from an existing local folder or cloned directly from GitHub into the configured Projects Root (normally `D:\Projects`). Forge records the detected GitHub remote in the project registry/passport and provides Open GitHub plus normal non-force source-control operations. The Project Workspace Source Control and Tooling pages are vertically scrollable so all categories remain reachable on smaller windows.

Tooling includes a capability matrix and **Build All Registered** operation. Build All runs sequentially and delegates each project to its strongest discovered authority: declared `project.control.json`, a project-native machine provider, a command-registry PCC such as Havenwild's `HavenwildTools.ps1 -Command ...`, an explicit PowerShell action provider, then finally conservative Rust/.NET/Gradle/Node/CMake/Python fallbacks.

On Windows, background health/status probes never allocate consoles. Git probing uses no-window execution, active health refreshes are serialized, and project output is normalized to UTF-8 so Unicode diagnostics cannot terminate the adapter.

## Vault workspace and Artifact Central

Vault remains the Forge workspace responsible for durable catalog/index data, patch intake, Artifact Central, baselines, recovery and storage migration. Cross-volume C:/D: transfers are copied to a temporary destination-volume file, SHA-256 verified, atomically promoted on that volume, then the source is removed.

## F41-F60 workflow shell

Vault 0.4 keeps the Python/Tk control and recovery surface and adds a collapsible workspace rail, collapsible 0-100 health gauge, native Windows tray lifecycle, structured Settings/Services, per-project Artifact Central, stricter build-bound patch intake, global tooling inventory, Cortex workspace integration and an optional Vault-themed Monaco IDE in its own pop-out window. The native editor remains available when optional web components are absent.

Modern Vault patches use `vault.patch.v2`: package-time evidence and target build/source preconditions are verified before staging. Legacy global downloads are retained for review rather than silently applied.

## Windows launchers

- `Vault.vbs` — preferred GUI launcher without a bootstrap console.
- `Vault.cmd` — visible diagnostic launcher.
- `VaultConsole.cmd --root <project>` — emergency console fallback.
- `VerifyVault.cmd` — source-package verification/self-test.
- Legacy `ProjectControlCenter.*` and `Forge.*` launchers remain compatibility aliases and launch Vault.

## F21-F40 milestone

F21-F40 makes Vault portable and removes global Downloads intake from project-gate authority. It adds a D:-first storage/project model, whole-drive project indexing, a dedicated Forgejo administration surface, expanded GitHub + Forgejo source control, portable project registry rebinding, and categorized command surfaces in the middle workspace column. See `docs/F21_F40_PORTABILITY_FORGEJO_SOURCE_CONTROL.md`.

## F11-F20 milestone

This milestone renames the application authority to Vault and upgrades the universal spine in the areas needed for real project use:

1. Vault is the primary application identity and storage authority; legacy Forge/PCC environment variables remain readable during migration.
2. Project discovery now recognizes nested project utilities such as `tools/control/StardewModdingKitTools.ps1`, including declared PowerShell `ValidateSet` actions and explicit `$Action` switch values.
3. Stardew toolkit roots are recognized as `stardew-toolkit`; SMAPI manifests and content packs are recognized separately.
4. .NET projects receive inferred `dotnet build`, Release build and quality-gate commands when no stronger project utility is available.
5. Vault Library scans now persist project discovery/tool-command capability data in addition to source/assets, duplicates, large files, invalid JSON, hashes and environment/toolchain inventory.
6. The GUI displays discovered source/tool-command counts and Build/Gate/Run capability in project details.
7. Intake watches both configured Downloads locations and project/application roots. Manifest-bearing ZIP transports are hash-verified into Vault before the loose source copy is removed.
8. A universal transactional patch engine is now the fallback when a project does not expose a stronger native patch authority. It validates paths, payload hashes/bytes, optional preimages, makes recovery copies, atomically writes files and rolls back on failure.
9. Root-drop and Downloads patches enter the same queue and are staged before Build/Quick/Fast/Full or explicit Apply Updates.
10. Vault can patch its own source. A successful Vault-targeted patch writes a restart-required marker; the GUI offers to restart so the new code becomes active.

## Stardew behavior

A project such as `C:\Users\Shifty\Desktop\SDMODDING` with `tools\control\StardewModdingKitTools.ps1` is no longer treated as scan-only. Vault discovers that utility and its explicitly declared actions and maps recognized actions such as Build, Full-Gate and Run-Game into the normal Vault operation surface. Unrecognized declared actions remain available in Advanced Commands. If an older utility is purely menu-driven with no declared action parameter, Vault still exposes the utility itself rather than pretending it has a build command that cannot be justified.

## Self-update behavior

The first move from the old `ProjectControlCenter-Standalone 0.10.2` into Vault requires a one-time bootstrap overwrite because 0.10.2 does not contain the universal transactional updater. After that bootstrap, normal Vault patch ZIPs can be dropped either into the Vault application root or the configured Downloads intake path.

For a Vault-targeted update:

1. Intake copies/hashes the transport into the durable Vault Library queue.
2. `Apply Updates`, Build or Full Gate stages it into `updates/inbox`.
3. `VaultPatchEngine` validates preimages and applies it transactionally.
4. The exact transport is retained in the applied archive with receipts/recovery evidence.
5. Vault reports that a restart is required and can relaunch itself.


## Default storage

Vault prefers `D:\Vault` on Windows when D: exists and otherwise uses the user's local application data directory. The durable Library is stored below that root. Overrides:

- `VAULT_DATA_ROOT`
- `VAULT_PROJECT_REGISTRY`
- `VAULT_STORAGE_ROOT`
- `VAULT_INTAKE_PATHS` (semicolon-separated on Windows)
- `VAULT_FORGEJO_HOSTS`

Legacy `FORGE_*` and `PCC_VAULT_ROOT` variables are accepted only for migration compatibility.

## Verification

```text
VerifyVault.cmd
```

or:

```text
python tools/VaultGate.py full
```

### Portable D: storage

Vault can relocate its durable home to `D:\Vault`, set `D:\Projects` as the portable project root, scan `D:\` for nested/composite projects, and migrate the active project through a hash-verified staged copy while retaining the original as rollback evidence.
## Source authority bootstrap

Forge can onboard a project from GitHub or attach GitHub authority to an existing local source tree. `Initialize / Adopt Git` is safe for an unborn `.git` directory: if the declared remote already has `main` history, Forge adopts that history as the local parent with a mixed reset while preserving current working-tree files. The current tree can then be reviewed, Full-Gated, committed through `Commit GREEN`, and pushed normally. GitHub repository hints may be declared in `project.control.json` and are also retained in the Forge project registry/passport.
