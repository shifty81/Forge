# ForgePY F743 — Native Rust Foundation

F743 is the next cumulative ForgePY/Rust migration slice. It retains every F742 Dashboard, gate-ordering, project-identity, and cancellation repair while replacing the single-file Rust placeholder with the first governed native foundation.

## Authority remains unchanged

Python ForgePY is still the production controller. Forge Native is in **SHADOW** phase and cannot claim takeover. The migration remains:

`DONOR → SHADOW → DUAL-READ → MIRRORED → CANDIDATE → PRIMARY → RETIRED`

Takeover is blocked until the parity matrix has no `MISSING`/unapproved `DIFFERENT` rows, migration/rollback is proven, the native Full Gate is GREEN, all production callers have moved, and takeover is explicitly approved.

## Native foundation introduced

`native/forge-rs` now owns real Rust modules for:

- native application identity and authority phase;
- project-contract read-only probe boundary;
- project path confinement and traversal rejection;
- operation state and cooperative cancellation token;
- transaction/checkpoint state with duplicate-target fail-closed behavior;
- explicit parity states and fail-closed takeover readiness;
- native probe, self-test, and parity JSON output.

The F743 native crate intentionally remains dependency-free. This isolates the first Windows Rust certification from GUI/database/runtime dependency problems and makes the first Cargo build a clean proof of the core source itself.

## ForgePY-driven Rust certification

`tools/rust/ForgeRustLane.py` now supports:

- `status`
- `check`
- `test`
- `build` / `build-release`
- `run`
- `probe`
- `parity`
- `gate`

When Cargo/rustc are available, the normal ForgePY Full Gate now executes the Rust SHADOW gate. While Python remains authority, a machine without Rust reports a visible warning/skip rather than invalidating the Python production gate. Once a Rust toolchain is available, broken governed Rust source fails the ForgePY Full Gate.

## ForgePY self Dashboard

ForgePY's self-management Dashboard now exposes a dedicated **Forge Native Rust Migration · SHADOW** panel with Rust Status, Parity Matrix, Rust SHADOW Gate, Build Native, and Run Native actions. Candidate and certified identities are displayed separately so `0.5.0-candidate.743 / FORGEPY-F743` cannot be confused with the certified `0.4.415-F60R415` donor identity.

## Project identity

`project.control.json` explicitly declares `assets/branding/ForgePY.png` as ForgePY's project icon and carries candidate identity metadata. The F742 project-aware quickbar resolver remains the active icon/name presentation for ForgePY and other registered projects.

## Next native wave

After the Windows authority machine compiles/tests this dependency-free foundation, the next native wave should add:

1. semantic project-contract/config parsing;
2. durable Catalog/storage authority using SQLite/WAL;
3. native process-tree host with streaming output, cancellation, bounded telemetry, and job leases;
4. secured local Forge host IPC;
5. then the native egui shell/Dashboard over those services.

The GUI should consume stable native services rather than becoming the place where operational authority is implemented.
