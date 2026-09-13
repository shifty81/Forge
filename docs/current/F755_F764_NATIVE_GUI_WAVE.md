# ForgePY F755–F764 Native GUI Wave

This wave makes the Rust successor a real desktop application instead of a headless SHADOW executable. Python ForgePY remains the certified operational authority until native parity is explicitly promoted.

## Passes

- **F755 — eframe bootstrap:** pinned `eframe 0.36.2`, `egui_dock 0.21.1`, image loading, persistence, and a real graphical launch path.
- **F756 — Forge visual shell:** dark ForgePY theme tokens, permanent left navigation rail, top project-aware quickbar, right Health rail, and bottom status bar.
- **F757 — docking workspace:** real `egui_dock` state with the Project/Dashboard and Forge Console split to match the current Python shell.
- **F758 — project identity:** native quickbar uses the selected project's discovered name/icon and the window uses the project icon when available.
- **F759 — foreground operation queue:** one active operation, visible pending queue, duplicate coalescing, project/root binding, and Stop cancellation.
- **F760 — embedded native console:** streamed PCC output, command composer, Send/Stop, bounded transcript, and safe command aliases.
- **F761 — health/status surfaces:** native health gauge, truthful SHADOW authority rows, project context, queue state, and Last Run status.
- **F762 — widget system:** Dashboard, Console, Native Migration, Project CLI, Vault, Workspace, and Settings are reopenable dock widgets that can tab/split/resize/undock.
- **F763 — persistence:** eframe storage persists dock layout and selected primary surface; Reset Layout restores the ForgePY default.
- **F764 — native launch/certification:** `Run Native` builds and launches the Rust GUI detached, passes the Python interpreter path to the native bridge, and retains headless audit/self-test modes.

## Authority rule

The native shell may call the existing governed PCC operation host while backend ownership migrates. This is intentional: the GUI is useful immediately without pretending unfinished Rust services are authoritative.

## Windows acceptance

1. `Rust SHADOW Gate` must compile/test/build the crate.
2. `Run Native` must open the graphical ForgePY window and return control to Python ForgePY.
3. The native window must show the ForgePY project icon/name, left rail, quickbar, docked Project + Forge Console, Health rail, and status bar.
4. Dashboard/Console tabs must drag, resize, split, close, reopen, and undock.
5. Full Gate/Build/Test must queue rather than emit an "already running" modal.
6. Stop must terminate the active process tree and produce `STOPPED` state.
7. Dock layout must survive restart; Reset ForgePY Layout must restore the default shell.
