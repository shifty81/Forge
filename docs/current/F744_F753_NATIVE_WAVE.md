# ForgePY F744-F753 — Native Migration Wave 1

This is the ten-pass continuation after F743. Python ForgePY remains the operational authority; Rust remains SHADOW and cannot take over.

## Passes

1. **F744 — GREEN callback bridge compatibility.** Preserve positional and keyword arguments through the legacy normalization wrapper so generation-aware post-gate callbacks cannot crash after a GREEN Full Gate.
2. **F745 — GREEN publication state/evidence.** De-duplicate publication by Full Gate generation and write a runtime receipt under `.forge/runtime/green-publication.json`. Publication failure remains distinct from quality-gate failure.
3. **F746 — SQLite lifecycle hardening.** Close exception-path Vault catalog connections deterministically rather than leaving garbage collection to report unclosed database handles.
4. **F747 — Native event protocol.** Add `forge.native.events.v1` request/event primitives and fail-closed request parsing for the Rust successor.
5. **F748 — Native process host.** Add streamed stdout/stderr collection, cancellation polling, and Windows process-tree termination through `taskkill /T /F`. Windows certification is still required before parity promotion.
6. **F749 — Native single-flight jobs.** Add one-active-operation queue semantics matching ForgePY's guarded execution model, including STOPPED cancellation terminal state.
7. **F750 — Native project/settings probes.** Add bounded project icon/name probing plus Vault/registry path snapshots without recursive project scanning.
8. **F751 — Native rollback journal.** Add confined filesystem checkpoint/rollback primitives as the first real transaction implementation behind the native patch lane.
9. **F752 — Native stdio IPC and evidence.** Add line-oriented request handling plus atomic parity-evidence receipt generation and ForgePY runner commands.
10. **F753 — Native shell model.** Add the canonical Vault / Project / Workspace / Settings shell model with project-aware name/icon context, and expose Evidence/Shell Model controls on the ForgePY self Dashboard.

## Authority boundary

`FORGEPY-F753` is still the Python product candidate. The Rust build identifies itself as `FORGE-NATIVE-WAVE1-0.3-F753` and remains `SHADOW`. `takeoverReady` stays false while catalog storage, full project-contract parsing, production transaction parity, host IPC certification, and the graphical native shell remain incomplete.

## Next native wave

The next priority is native SQLite/WAL catalog storage, then production-grade project-contract/settings parsing, Windows process-host certification, and the first graphical egui/eframe application shell.
