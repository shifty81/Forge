# Forge unified source — consolidation pass C01 (19 September 2026)

**This is a complete STAGING SOURCE ROLLUP, not a root-drop patch and not a certified replacement of an existing installed Forge.** The ZIP has no extra top-level wrapper; extract to a new empty directory. Never extract over an existing checkout without a reviewed diff. The original user archive and its ZIP transports have not been applied or deleted from the original source.

## What this is

- **One existing Forge/ForgePY repository source tree:** original `app/`, `native/forge-rs/`, project-local PCC/CLI, tools, tests, assets and governed documentation. No standalone P0B/P0C scanner code is included.
- Original ForgePY `VaultDriveIndex.scan` and its SQLite catalog remain authoritative; both `app/ForgeGui.py` and the expanded `app/ForgeUnifiedCli.py` route to that existing backend. Native Rust's Vault panel delegates its Scan and Catalog Summary buttons to the same Python CLI and catalog rather than creating a parallel scanner.
- Native selected-project operations now resolve the **central verified Forge backend** and pass the selected project root through `ForgeUnifiedCli.py command run`. They do not execute a Python backend guessed inside a selected game repository.
- GitHub clone destinations are owner-qualified; reuse of existing checkouts requires a matching real Git remote, including legacy flat-layout clones. No automatic batch clone or repository rename takes place.
- Passive version/identity probes parse string constants with `ast` instead of executing arbitrary version modules. CLI patch-queue/preflight failures and nested service errors now return nonzero status.
- An unlisted but present `native/forge-rs/src/bin/forge_tool.rs` was recovered from the original ZIP to make the declared `ForgeTool` target structurally complete.

## Use on Windows

1. Extract the COMPLETE source ZIP to a new, empty checkout directory. This archive is not a PCC update transport; do not drop it into any live repository root's watched update queue.
2. Run `VerifyForgePY.cmd` from the new root for self-test and quick gate. `ForgePY.cmd` launches the existing operational Python app.
3. Read `docs/consolidation/UNIVERSAL_FORGE_SPEC_V1_DRAFT.md` and `docs/consolidation/VALIDATION_AND_SOURCE_HANDOFF.md` before any promotion.
4. For a scoped scan of your D: drive using the **existing ForgePY scanner**, run `python app/ForgeUnifiedCli.py --json vault scan --scan-root D:\` in this staging checkout. This creates/updates ForgePY's configured Vault catalog; check Vault settings and ensure there is sufficient space before a large scan. It does not clone, move or register projects.
5. `python app/ForgeUnifiedCli.py --json vault catalog-status` reads the same persisted scan. Native Vault buttons reach this CLI when Forge Native is built and launched with `FORGEPY_HOME` pointing to this root.
6. To test Rust SHADOW: use `python tools/rust/ForgeRustLane.py gate --root .` with Cargo/rustc available. Never promote native authority solely because the Python quick gate passed.

### Verified here

- Original archive ZIP CRC and 487 declared manifest files' hashes checked; recovered one additional Rust bin source missing from the old manifest.
- Python syntax checked and existing Python quick gate passed on a disposable Linux staging checkout.
- The isolated Python test suite passed after the missing Rust source was recovered; the final gate log contains the exact current count. The Python Full Gate runs Rust only if Cargo/rustc are present and must not be treated as native certification if that stage is skipped.
- **Not verified:** Windows compilation, Rust cargo check/test/build, live D: scan, live GitHub clone/rename, actual user's current checkout parity, production installer or full runtime certification.

## What still needs implementation

- Resumable/checkpointed whole-drive census without collecting all entries in RAM, Windows reparse safety policy, source lineage confidence and approval queue.
- GitHub account-wide inventory, permission-aware repository rename review/confirm and remote reconciliation, first-class clone plan and approval from the Forge panel. Existing GUI single-clone button is retained, with strengthened backend identity checks.
- Reconcile the separate ForgeGUI_Core donor and the F1001–F1125 in-archive root-drop only against exact current native preimages and a passing Rust build. Those root drops were **not** silently applied over this newer F976 source.
- Durable one-writer forge.operations.v1 across process boundaries, Cortex CLI adapter, Ember integration and formal spec approval.

No user source, D-drive data, Github repository or live installation was changed while preparing this rollup.
