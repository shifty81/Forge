# Forge Native Rust successor

`native/forge-rs` is the governed Rust successor to ForgePY. It is **not** the operational authority yet.

## Current phase — SHADOW

F753 expands the bootstrap into a dependency-free native foundation that models:

- application identity and migration authority phase;
- project-contract probe boundaries;
- project path confinement;
- operation/cancellation state;
- transaction/checkpoint state;
- explicit parity states (`PASS`, `MISSING`, `DIFFERENT`, `INTENTIONALLY_SUPERSEDED`);
- fail-closed takeover readiness.

The dependency-free foundation is deliberate: the first Windows Rust certification can validate Cargo/rustc and the core contracts without simultaneously introducing GUI, SQLite, async runtime, Git, or installer dependencies.

## Commands

From the repository root, ForgePY owns the lane:

```text
python tools/rust/ForgeRustLane.py status --root .
python tools/rust/ForgeRustLane.py check --root .
python tools/rust/ForgeRustLane.py test --root .
python tools/rust/ForgeRustLane.py gate --root .
python tools/rust/ForgeRustLane.py probe --root .
python tools/rust/ForgeRustLane.py parity --root .
```

A passing SHADOW gate does not authorize takeover. Python ForgePY remains production authority until the full parity matrix is verified and takeover is explicitly approved.

## F744-F753 native wave

The first migration wave adds callback-safe Python completion compatibility, a versioned native event protocol, single-flight job state, streamed process execution with cancellation, bounded project/settings probes, filesystem checkpoint rollback, stdio service endpoints, atomic parity evidence, and a project-aware native shell model. Python ForgePY remains operational authority.
