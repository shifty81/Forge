# Universal Forge — specification finalization register v1 (DRAFT)

**Status:** proposed for approval. Implementation and certification statuses below are evidence-based, not inferred from an audit-kit test. Forge is the standalone universal project workstation, not a special-case Cortex or game editor.

## 1. Product and source authority

| Domain | Canonical implementation / policy | Status in this rollup |
|---|---|---|
| Product / project ID | One root repository: Forge application, historically identified by `forgepy` in `project.control.json`. Do not rewrite stable IDs as a branding operation. | Existing |
| Operational backend | Existing ForgePY Python `app/` + Forge-owned universal PCC/protocol + project-owned PCC adapters. | Existing; quick gate passes |
| Native interface | `native/forge-rs` Rust eframe/egui tool host, SHADOW; adapt existing backend, not parallel sources of truth. | Bridge and Vault panel hooked; Rust build not run |
| Universal GUI library | ForgeGUI_Core independent donor with pinned version/source hash, shared 2D/3D and app chrome; attach behind native adapter. | Donor unmerged; F1125 root-drop needs preimage review |
| Cortex | Optional intelligence/chat/models/agents client of Forge operations, not hidden second PCC/CLI/patch executor. | Contract pending |
| Ember | Host/editor workspace using Forge operations, project registration and reusable GUI. | Integration pending |
| Hosted game projects | Independent project source and project-owned PCC/Git authority; register adapters, do not flatten gameplay into Forge. | Boundary retained |

**Repository identity trap:** the separate GitHub repo called `shifty81/ForgePY` currently contains an unrelated Lua EmployeesPlus mod, whereas `shifty81/Forge` holds the ForgePY/Forge application. Match identity from source/contract, not repository name. Local checkouts may be newer than either public commit; require source hashes before update.

## 2. ONE scanning/catalog authority

The canonical machine-wide scanner is **`app/VaultDriveIndex.py:scan()`**, backed by `VaultPaths.vault_root()/catalog/drive_index.db`, with the existing `PCCProjectDiscovery`, `PCCVaultCatalog`, `ForgeDriveCensus`, classification, ownership and lineage services. `ForgeGui.py` already exposes Scan D Drive. This rollup exposes the **same scanner** through `ForgeUnifiedCli.py vault scan`, and adds native Vault actions delegated through the central Forge backend. Do not copy the separate P0C2 `universal_audit.py` implementation into production. Its UX/checkpoint ideas are only candidates for a careful upgrade of the existing scanner.

Scanner certification requirements: index every accessible file within user-authorized roots without silently following junctions/reparse points; classify independent/nested projects, duplicate/version lineage, assets, code, archives, patch transports; durable checkpoints and resumable cursor; bounded memory, progress, cancellation and errors; stable file/project identities, hash-on-demand, SQL migrations; no source moves/deletes/registration unless approved; never overwrite an existing catalog with incomplete/truncated results; drive scan does not treat old Downloads files as approved updates. **The current `VaultDriveIndex.scan` materializes all raw entries before SQLite classification, and a max_dirs interruption is truncated rather than checkpoint-resumable. These remain OPEN; do not claim P0C2 behavior was ported.**

## 3. ONE source/remote authority

Existing Forge source/Git and ForgeGit remain canonical; GitHub is mandatory mirror/provider, not a replacement for internal history. Reconcile remote repository identity with local `.git` URL and ID, distinguish flat legacy clone vs owner-qualified clone, detect collisions, diverged branches, working-tree changes, Git LFS, submodules, detached/shallow repos, and no-remote project copies. Default clones into owner/repo, keep donor repos independently usable. This rollup fixes single-clone collision/remote reuse and does **not** enumerate, bulk-clone or register the account.

GitHub panel next: authenticated paginated inventory (including private accessible repos), status/permissions, fetch/pull/push with protected-branch policy, branch/PR review, repo rename. Rename must preview old/new owner/name, validate authenticated admin permissions, confirm exact repository slug, check name collisions, create pre-change receipt, execute via official GitHub API, re-fetch canonical ID/name/clone URLs, reconcile approved local remotes/links, report failures and any non-redirected integrations. A source-tree rename or GUI label edit alone is NOT GitHub repository renaming. No remote mutations from passive scans.

## 4. ONE operations and update spine

`forge.operations.v1` proposed durable provider envelope: hello/capabilities, register project identity, status/submit/events/cancel/receipt; global operation ID, project identity, typed risk and approval, one writer per project with leases and recovery; stdout structured JSONL and stable exit codes; preserve independent project PCC ownership. Existing Python operation services remain sole execution authority; Rust native queue delegates via central Python `ForgeUnifiedCli.py`, and Cortex/Ember will consume service contract when implemented. Native in-memory queue isn't durable; no parallel executor promotion.

Patch/update: project inference by manifest, paths, SHA/preimages, branch lineage and project contract; ambiguous changes fail into Review; preserve stale patches in inert Vault lineage; transactional backup/apply/verify/rollback/archive; Full Gate must not implicitly apply an unapproved historical root ZIP. No source moves/deletes without explicit review. Self-update uses exactly same transactional update authority.

## 5. GUI and spec governance

Maintain one universal dimension-agnostic ForgeGUI_Core library with shared widgets/docking/theme/chrome and context-driven 2D/3D viewports. Product-specific Forge Python UI is operational bridge during native SHADOW; do not create additional standalone audit GUIs or sidecar libraries. Every major capability has an owner, typed schema, conformance tests, cross-app adapter, backwards compatibility, runtime/gate evidence and approval state. Source authority, CLI, Vault, onboarding, Git/GitHub/ForgeGit, patch lineage, recovery, operations, GUI, project PCC, Cortex, Ember, model/tool providers, security, installation, updates and quality gates must be finalized together; draft text alone does not implement them.

## 6. Required promotion gate (all required)

1. Verify actual user's latest checkout source hashes/branch/dirty state and original archive lineage before applying ANY patch.
2. Reproduce Python Full Gate on Windows with clean source and isolated Vault; record smoke, whole-suite results, GUI launch and logs.
3. Cargo check/test/build BOTH ForgeNative and ForgeTool; confirm Rust backend path resolution with an independent sample project's PCC; test cancellation/exit, stdout JSONL and missing-provider behavior.
4. Same-scanner parity: Python UI, CLI and native UI scan the same tiny fixture and produce the same DB/ProjectId/entry classifications; then bounded D: staging scan and resume under realistic filesystem cases.
5. GitHub inventory/clone/repo-rename use a test account/repository with consent, backup/receipt and no leaked tokens; verify local and ForgeGit remote reconciliation.
6. Patch lineage and rollback fault injection, no unauthorized auto-apply, source package hashes, executable/installer smoke and green-source attestation.
7. Cortex/Ember callers use the shared operations provider and cannot bypass Forge approvals. Semantic spec approval tracked in one canonical roadmap, with all currently OPEN items explicit.

**Takeover:** Rust remains SHADOW until all native parity/gate requirements are met and explicit promotion approval is recorded. This draft is NOT a GREEN certification.
