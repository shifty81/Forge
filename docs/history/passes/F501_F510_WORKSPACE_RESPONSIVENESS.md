# ForgePY F501-F510 — Workspace Responsiveness Repair

This block is cumulative with F450-F500.

## Root cause

The legacy Workspace/IDE path synchronously called `_ide_refresh_files()` from the tab builder.
The tab switch routine then immediately called the same method again. `_ide_refresh_files()`
walked the active project filesystem and inserted the entire file list into a Tk Treeview before
returning. Large projects could therefore block the Windows message loop long enough for ForgePY
to display as Not Responding.

## Repair

- Workspace file enumeration now runs on one background worker.
- Duplicate first-open refreshes for the same project are coalesced.
- Worker threads never create/update Tk widgets.
- Results are polled from the Tk thread.
- Tree insertion is performed in batches of 250 entries.
- Tk receives an event-loop turn between batches.
- Workspace shows `Scanning project files…` immediately.
- Switching projects invalidates stale scan generations.
- A stale scan result is never populated into a newly selected project.

## Audit worker repair

The registered-project audit worker previously wrote status text through GUI logging from its
background thread. The F501-F510 workflow now returns audit results to a Tk-thread poller before
touching GUI state.

## Policy

`ForgeWorkspacePerformance.policy()` reports the enforced responsiveness contract. Cortex and
diagnostics may consume this later when checking UI/runtime health.
