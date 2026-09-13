# ForgePY F511-F520 — Workspace Instant Open

This block is cumulative with F450-F510.

The remaining Workspace delay came from the legacy IDE panel constructor itself. It still
performed optional Monaco/pywebview readiness work on first open and retained a whole-tree IDE
model even after enumeration moved off-thread.

F511-F520 replaces that user-facing builder with a lightweight native Workspace:

- no Monaco import/readiness check while opening Workspace;
- no pywebview import/readiness check while opening Workspace;
- no Monaco installer/window controls in normal Workspace;
- cheap Workspace widgets are prebuilt during an idle callback after startup;
- prebuild performs no project scan;
- first Workspace click paints immediately, then starts file enumeration asynchronously;
- file index is cached for the active project and reused when switching tabs;
- only immediate root entries are rendered after scan;
- directory contents materialize only when that folder is expanded;
- file reads occur on a worker and update the editor on the Tk thread;
- changing project invalidates stale Workspace results without doing synchronous I/O.

Project Console remains beside Workspace and is still the shared execution surface for future
Cortex integration.
