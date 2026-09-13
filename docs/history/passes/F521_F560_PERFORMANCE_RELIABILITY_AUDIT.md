# ForgePY F521-F560 — Whole-Project Performance & Reliability Normalization

This package is cumulative with F450-F520 and remains a direct root overlay.

## Audit conclusion

The remaining responsiveness defects were systemic rather than one Workspace bug.

### HIGH — project selection performed discovery/Git work on Tk

The registered-project selection callback synchronously built `ProjectContract`, `BackendClient`,
read Vault catalog state, and resolved GitHub/source state. Selecting a row therefore did real
project discovery before Tk could return to the event loop.

**F521-F545:** selection is now instant preview-first with a debounced background metadata load.
Rapid keyboard/mouse selection does not fan out workers. Results are generation-scoped and cached.

### HIGH — activation repeated project discovery and source probing

Project activation ran repository hygiene first, loaded the contract, built the backend, then
`ProjectRegistry.touch()` rediscovered the contract and resolved GitHub again before writing the
registry/passport. It also refreshed secondary GUI surfaces before showing the selected project.

**F521-F545:** activation is an asynchronous transaction. Contract/provider/source state is
discovered once in the worker, registry/passport use the preloaded result, Project Dashboard is
shown before secondary command-list rendering, and repository hygiene is deferred/backgrounded.

### HIGH — one routine health snapshot duplicated Git work

The generic status path had its own Git status/branch/head/ahead-behind probes and then called
the canonical source-control status function, which performed another series of Git processes.

**F533-F538:** routine GUI/health status uses a shared short-TTL `ForgeStatusCache`, normally two
Git processes: porcelain-v2 status plus remote listing. Exact source-control commands remain
authoritative for mutations/review.

### HIGH — routine GREEN display could hash the repository

Exact GREEN verification can enumerate governed files and SHA-256 each file. That belongs at
certification/commit verification boundaries, not in a recurring GUI health refresh.

**F533-F538:** compact status uses a conservative fast GREEN check: a GREEN marker is considered
matching only when the working tree is clean and current HEAD equals `gitHeadAtGate`. Exact
fingerprint verification remains available to gate/source authority.

### HIGH — independent recursive scanners could saturate one disk

Drive census, Vault indexing, project cataloging, tooling audit, artifact indexing, IDE discovery,
and other maintenance systems can independently perform large recursive scans.

**F521-F550:** ForgePY now has a process-local Load Coordinator. Known GUI-owned deep scanners
share one disk-heavy scan lane when running in workers. User interaction delays new background
scans. Startup drive census is deferred from roughly five seconds after launch to an idle period
roughly thirty seconds or later.

### WARN — job persistence could grow and race

The job queue persisted the whole in-memory history from several worker transitions, with no
dedicated persistence lock and no history pruning.

**F551:** job history is bounded, completed futures are discarded, and jobs.json uses serialized
atomic temp-file replacement.

### WARN — the GUI remains a large import-coupled module

The certified baseline `ForgeGui.py` is a large module and eagerly imports many subsystems.
The overlay intentionally does not overwrite the user's newer candidate GUI. Long-term executable
normalization should continue moving implementation behind Vault/Project/Operation/Workspace
services rather than growing that monolith.

### WARN — root app/ versus nested ForgePY/app

`app/` remains canonical. The nested `ForgePY/app` mirror/reference can confuse package collectors
or execute divergent code if it drifts. The new audit reports identical/divergent duplicates.

## Runtime telemetry

ForgePY now records meaningful event-loop stalls as `ui-event-loop-lag` and exposes:

- `forge performance recent`
- `forge performance recent --slow-only`
- `forge performance load`
- `forge performance audit`

The static audit reports recursive scans, synchronous subprocesses, subprocesses without timeout,
whole-file reads inside loops, raw threads, extra thread pools, large Python modules, GUI hot-path
heavy calls, syntax errors, and duplicate source authority.

## Executable readiness

ForgePY is close to a packaged executable candidate, but responsiveness should be certified before
freezing the Python application.

Remaining checkpoints:

1. Apply this cumulative overlay and prove Vault/Project/Workspace switching remains responsive
   across the actual project library.
2. Run Full Gate plus a normal interactive soak and inspect slow performance events.
3. Repair any live-candidate-only defects surfaced by `forge performance audit`.
4. Add the Windows executable packaging lane with deterministic module/resources, no nested mirror
   authority, startup diagnostics, portable data-root behavior, and self-update compatibility.
5. Certify the packaged executable through project switching, patch intake/apply, source control,
   Full Gate, Workspace, diagnostics and shutdown/relaunch.

The executable milestone is packaging/hardening after this checkpoint, not another architecture
rewrite.
