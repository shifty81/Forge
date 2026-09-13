# ForgePY F391-F415 — Simplified Operator Workflow

Baseline: `FORGEPY-F60R390` / commit `f1ac23cee4e9f3c69e6cfec42d3deb89341e8fe6`.

This tranche keeps the existing validation, patch, Vault, project-provider, Git and recovery authorities but removes their internal states from the normal operator path.

## Daily project workflow

The selected-project Dashboard is the normal control surface. Its permanent primary actions are:

- **FULL GATE** — run the project-owned authoritative Full Gate. GREEN automatically commits and publishes the active branch to GitHub.
- **BUILD** — run the project-owned build operation.
- **RUN** — run the project-owned runtime operation.
- **CHECK FOR UPDATES** — scan Downloads/intake, classify candidates and surface only actionable work.
- **APPLY + FULL GATE** — shown through the update/intake flow after ForgePY proves a safe target.

Manual approval, routing, queue internals, receipts and raw patch staging remain available as advanced diagnostics/recovery mechanisms; they are not the ordinary workflow.

## Patch intake

The Health rail carries the visible patch-folder intake target directly above the global ForgePY version. Clicking it opens the patch picker. On Windows, Explorer file drop is enabled on the ForgePY top-level window and routes `.patch`/ForgePY patch-package files into the same intake function.

Intake always resolves the transport across registered projects. The selected project is never blindly treated as patch authority. A unique compatible project is used automatically. Ambiguous resolution fails closed and requires one explicit project choice. Existing Vault intake continues to own historical/superseded/already-applied classification and lineage.

After the one meaningful approval, ForgePY queues through the existing validated intake authority, applies through the existing guarded patch command, and chains successful application directly into Full Gate.

## GREEN publication

A GREEN Full Gate is the normal source-control boundary. ForgePY starts the existing GREEN-protected commit/push operation without a second operator prompt. The current branch is preserved. Remote non-fast-forward/divergence failures remain fail-safe; ForgePY never force-pushes automatically. In that case project certification remains GREEN while remote state is reported as pending.

## Source Control

The normal Source Control workspace is reduced to two tabs:

1. **Local Source** (default) — Backup Source, Restore Source, Create Branch and Switch Branch.
2. **GitHub** — remote status, Backup to GitHub and guarded Restore from GitHub.

The existing `ForgeGit` implementation remains a compatibility/internal service; **Local Source** is the operator-facing term.

Local Source restore recovers a selected stored branch into a new local recovery branch instead of force-resetting the current worktree. GitHub restore uses the existing fast-forward-only source operation and refuses dirty/divergent destructive replacement.

## Debug handoff

Full Gate failure starts one project debug-bundle operation. The DEBUG control reveals the current canonical bundle in Windows Explorer with the file selected, making it directly draggable into ChatGPT. Automatic bundle generation does not automatically open Explorer.

## Project-specific operations

The left project rail may add **PROJECT TOOLS** groups, but only from `ForgeToolRegistry` entries with state `VERIFIED`. Detection by itself cannot create a user-facing button. Tools are grouped by their project-declared category and execute through the existing ForgeToolRuntime authority.

This is where certified Blender, Blockbench, cooker, worldgen, migration, replay, packaging or other project-owned CLI lanes appear when a project's audited adapter actually provides them.

## ForgePY compatibility reference

ForgePY maintains a small read-only, Vault-side compatibility snapshot per project. It records the exact ForgePY version/build and copies the current ForgePY project contract/version authorities for adapter/patch compatibility auditing. It does **not** vendor or fork the standalone ForgePY application into project source trees.

## GUI normalization

- oversized top ForgePY title strip removed;
- compact quick bar with selected project on the left and Refresh / Project CLI on the far right;
- selected-project Health rail forced visible;
- Health footer carries project/build, DEBUG, patch-folder intake and ForgePY version;
- compact bottom status reports project and Git/branch state;
- dark ttk scrollbars;
- Workspace navigation is labeled Dashboard;
- the old everyday COMMIT + PUSH button is hidden because GREEN owns publication.

## Certification boundary

This patch is a candidate until it runs on Windows through ForgePY's own Full Gate. The Full Gate is also updated to refresh the package manifest when source changes make the committed manifest stale, allowing the new source files/version to be certified and then included in the automatic GREEN commit.
