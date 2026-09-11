# ForgePY

**Current certified development build:** `0.4.45-F60R45` (`FORGEPY-F60R45`)

ForgePY is the standalone, local-first universal project operations application. It discovers a project's own CLI/PCC authority and provides the common GUI for build, run, quality gates, logs, updates, GitHub + ForgeGit source control, Artifact Central, Vault storage, diagnostics, and project tooling. Projects remain independently buildable without ForgePY.

## Canonical root

The installation root is now intentionally ForgePY-centered:

- `ForgePY.vbs` — preferred no-console GUI launcher.
- `ForgePY.cmd` — diagnostic/console-visible launcher.
- `ForgePYConsole.cmd` — emergency console surface.
- `VerifyForgePY.cmd` — self-test + quick quality gate.
- `PublishForgePYRepository.cmd/.ps1` — repository publishing helpers.
- `FORGEPY_PACKAGE_MANIFEST.json` — release package authority.
- `project.control.json` — ForgePY's own project contract.

`Forge.cmd`, `Forge.vbs`, `ForgeConsole.cmd`, and `VerifyForge.cmd` remain tiny compatibility aliases so existing shortcuts and F60-era updates do not break. Older `ProjectControlCenter.*` and `Vault.*` launchers are no longer canonical root surfaces and live under `compat/legacy-launchers/`.

## Product boundaries

**ForgePY** is the application. **Vault** is ForgePY's storage/artifact/patch-lineage workspace. **Project Control Center / PCC** describes the project-owned control contract/spine that ForgePY can discover and invoke; PCC is not the product name. **Forgejo** is an optional compatibility/source-hosting integration, while Git/GitHub and ForgeGit remain source-control responsibilities.


## Branding

The canonical application artwork is `assets/branding/ForgePY.png`; `assets/branding/ForgePY.ico` is the Windows multi-resolution icon derived from that exact approved artwork. ForgePY applies the icon to the desktop window and native system-tray surface.

## Source control authority

GitHub is the standard external source authority and **ForgeGit** is the standard local source authority. ForgeGit uses ordinary bare Git repositories under the configured ForgePY home and binds them through the canonical `forgegit` remote (legacy `forgepy-internal` remotes are adopted). It does not create commits from dirty working files; project-owned certified GREEN commit workflows remain authoritative. Forgejo is retained only as optional compatibility/source-hosting infrastructure.

## Update model

ForgePY can register itself as a project and update through the same validated patch intake pipeline used for other projects. The canonical Downloads filename is `ProjectName__YYYYMMDD__Version.patch`. The package manifest remains authoritative; the filename is routing metadata only. Downloads discovery is non-executable until explicit approval. ForgePY self-updates use a dedicated transactional self-update lane, while ordinary projects continue through the universal project/PCC workflow. The legacy literal `incoming.patch` path remains compatibility-only.

## Development

Run `VerifyForgePY.cmd` for the quick gate or `python tools/ForgePYGate.py full` for the complete self-hosted gate. Historical PCC/Vault bootstrap material is retained under `docs/history/` and `reference/` for provenance only.


## Vault drive catalog

Vault Drive Catalog indexes the entire configured Vault drive rather than treating every detected marker as an equal project. It records files, directories, classifications, project/component ownership, patch transports, archives, generated/cache content, unassigned content, and conservative project-family/lineage hints. Drive cataloging is non-destructive; any later relocation/cleanup workflow must be explicit and governed.

## Patch Review / Routing

Fresh patch candidates and compatibility-review items across all registered projects are exposed in one decision surface. Operators can queue, queue-and-apply, archive to lineage, ignore, or reveal a package. Old/superseded evidence belongs in Patch Lineage; newly downloaded current packages must remain actionable rather than disappearing into historical storage.
