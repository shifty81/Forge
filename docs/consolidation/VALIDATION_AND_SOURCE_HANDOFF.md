# Consolidation C01 — source exact evidence, changes and remaining blockers

## Source ledger

- Input: `ForgePY (2).zip` (Library Sep 17, original ZIP SHA-256 `0c3430ed6a73f39b9bd32dc2767b7eab3543712f80746445e63f7e9048aeb476`). Original untouched. Main content under `ForgePY/` ZIP wrapper; staged output uses repository root directly.
- 898 archive entries, ZIP CRC checked; `FORGEPY_PACKAGE_MANIFEST.json` declared 487 files and every declared file's SHA-256 and byte length matched the archive.
- Three **root-drop ZIP transports** excluded from clean source root, recorded with hashes in `SOURCE_PROVENANCE.json`; never executed/applied. `native/forge-rs/README.zip` is a second nested Rust snapshot, excluded after recording checksum. It is not a substitute for actual current Rust source.
- Unlisted but physically present `native/forge-rs/src/bin/forge_tool.rs` restored from same verified original ZIP; original manifest omission caused existing modular tool test to fail and made the Cargo `ForgeTool` declaration incomplete. The manifest generator and gate now check this Rust source and detect missing governed entries.
- External published `shifty81/Forge` at pinned F797 snapshot is **older/different** from the provided ZIP's F976 native handoff. The GitHub `shifty81/ForgePY` name is the wrong (Lua mod) product. Do not cherry-pick it by basename.

## Source-level corrections (C01)

1. `app/ForgeProjectSource.py`: GitHub owner-qualified clone path, reject unsafe/ambiguous URL/Windows reserved path, require actual matching remote before checkout reuse, safely reuse exact verified legacy flat clone, verify remote after clone.
2. `app/ForgeUnifiedCli.py`: `vault scan` / `catalog-status` call EXISTING `VaultDriveIndex`; forward progress to stderr, JSON result stdout, nonzero missing/truncated result. Patch queue and executable preflight fail nonzero on errors; operation result honors typed return code and error state.
3. `app/VaultBuildIdentity.py`: parse VERSION/BUILD constant assignments from untrusted version scripts instead of executing them.
4. `app/ForgeUnifiedServices.py`: nested backend error yields failure and emits failure event, not an `operation.result` success indicator.
5. `native/forge-rs/src/gui/operations.rs`: dispatch via **central** backend, not selected game's `app/PCCOperationHost.py`; fail closed when backend missing. Special `vault.scan` and `vault.catalog-status` commands use the same ForgePY catalog.
6. `native/forge-rs/src/gui/widgets.rs`: native Vault tab has scanner/summary actions that use canonical ForgePY backend, no new Rust scanner/database.
7. `tools/rust/ForgeRustLane.py`: seed `FORGEPY_HOME` for Rust launched through the canonical lane; native helper binary remains SHADOW.
8. `tools/BuildForgePYManifest.py` and `tools/ForgeGate.py`: retain Rust `src/bin` source in package manifest and compare complete governed file list before passing the gate.
9. `tests/test_forge_consolidated_spine.py`: fixture tests for all above Python pathways (no user D: or GitHub mutation), including original catalog persistence and manifest coverage.

## Verification ledger

| Gate | Result | Scope |
|---|---|---|
| Original 487-manifest SHA and ZIP CRC | PASS | Original available source only |
| Python parsing / syntax | PASS | Source, tools, tests, nested Python |
| ForgePY quick gate | PASS | Staged isolated Linux fixture, Python authority |
| Existing + new unittest suite | PASS, final count in gate log | Isolated home, original project fixtures |
| Manifest regeneration and ZIP CRC / independent extraction | To be completed at packaging | Full clean rollup |
| Rust `cargo check/test/build` | NOT RUN, cargo/rustc unavailable in execution container | Windows required |
| Windows self-test, GUI runtime, installer, full D: scan | NOT RUN | On user machine |
| Live GitHub account/ForgeGit mutation | NOT RUN | No remote mutations |
| F1001–F1125 root-drop application | DELIBERATELY NOT APPLIED | Targets F797; source has newer F976 Rust files; must reconcile preimages and compile first |
| Full project migration and native parity | OPEN | No promotion |

## Integration status and next named milestones

- **C02**: Reconcile user's latest local checkout with this staged ZIP and separately downloaded exact ForgeGUI_Core donor; review F1125 per-file Rust diffs before merge and run native build.
- **C03**: Upgrade `VaultDriveIndex` itself with bounded-memory SQL checkpoints/resume/reparse handling; one scanner in all surfaces.
- **C04**: Build GitHub panel inventory/repo rename with authenticated permission checks, explicit approval, receipts and local remote reconciliation. No mass cloning without individual/batch plan confirmation.
- **C05**: Durable `forge.operations.v1` one-writer service, Cortex CLI bridge and Ember clients, cross-project trace IDs.
- **C06**: Windows Full Gate, cross-app parity, rollback/installer smoke; only then prepare transactional overwrite patch against verified user's real preimage.

**Deployment:** use this clean full-source ZIP in a NEW checkout. It is not an overwrite patch for a newer local version, not a production installer, and is not a claim to have merged all independent software/game repositories into one physical Git tree.
