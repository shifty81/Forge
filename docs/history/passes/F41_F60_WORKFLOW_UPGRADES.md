# Vault F41-F60 Workflow Upgrades

Vault remains a Python/Tk standalone recovery and operations application. F41-F60 strengthens the shell around that proven control surface rather than replacing it.

## Shell layout

- The old top-level Projects / Project Workspace strip is replaced by a collapsible left **VAULT WORKSPACES** rail.
- The rail order is: Projects, Project Workspace, Vault, Forgejo, IDE, Cortex, Settings.
- Expanded and collapsed state persists in Vault settings.
- A right-side **VAULT HEALTH** rail displays active-project health as a 0-100 gauge and can collapse to a narrow border tab.
- Health components are Provider, Git, GREEN, Sync, Updates, Hygiene and Tooling.

## Windows tray contract

On Windows Vault owns a native Shell_NotifyIcon notification-area icon. The window can minimize or close to tray without ending background intake/source services. Double-click restores Vault. Vault also re-registers its notification icon after a Windows Explorer/taskbar restart. The context menu exposes Projects, Workspace, Health, Full Gate, Apply Updates, intake scan, Source Control, Forgejo, Vault IDE, Cortex, Settings, storage locations and explicit Exit.

Tray behavior is optional and fail-soft: if the Windows shell integration cannot initialize, the main application remains usable.

## Settings workspace

Settings now has dedicated pages for Services, Storage, Intake & Artifacts, Source Control, IDE, Tooling, Components, Cortex, Security and Interface.

Services are configuration-driven rather than hard-coded into project adapters. Storage authority can live on D:\ even when the Vault application itself is launched elsewhere.

## Vault IDE

The recovery editor stays inside the Tk application. Monaco is an optional **separate Vault-owned pop-out window**, not an embedded dependency of the main recovery GUI.

The Monaco host:

- runs in a separate Python process;
- serves only the local Vault Monaco runtime on 127.0.0.1;
- confines file read/write RPC to the active project root;
- uses a Vault-specific dark/cyan theme;
- supports Ctrl+S and project file navigation;
- falls back to the native Tk editor if Monaco/pywebview is unavailable.

This preserves a working editor even if WebView2, Node/npm, Monaco or the web host is unavailable.

## Artifact Central

Operational artifacts are centralized under the configurable Vault Artifact Central root while source remains in its governed project working tree.

`ArtifactCentral/projects/<project-id>/` contains:

- patches
- debug-bundles
- source-rollups
- builds
- releases
- baselines
- logs
- reports
- asset-intake
- backups
- review

Transfers are hash-verified and receive artifact receipts before source copies are removed.

## Patch verification v2

Modern Vault patches use `vault.patch.v2` and are expected to carry:

- canonical patch ID;
- package creation timestamp;
- target project identity;
- target build/source identity preconditions;
- payload hashes and byte sizes;
- path-safe payload operations.

Intake cross-checks the declared package time against ZIP evidence, rejects impossible future timestamps, verifies quarantine copies by SHA-256, and re-verifies the target project build/Git/GREEN identity immediately before staging/application.

Legacy unbound patches discovered globally are retained under Artifact Central `review/` instead of being silently applied. A deliberately dropped project-root legacy patch remains available as a compatibility path until all project patch producers emit v2 manifests.

## Tooling authority

Vault inventories existing project tooling before inventing adapters. It reads project contracts, tool registries, root launchers and conventional tool/script folders and classifies tools by domain. It never executes discovered scripts merely because they were found.

The global tool index is designed to become Cortex's searchable machine-operation inventory.
