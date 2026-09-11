# ForgePY F60R389 — Unified GUI + Command Console

Every top-level workspace now shares one operating structure:

`Workspace rail | Quick Actions + active workspace | Project Console | Health rail`

The persistent console remains visible in Projects, Project Workspace, Vault, Source Control, IDE, Cortex and Settings. Its bottom command entry merges ForgePY meta commands with the active project's declared `project.control.json` commands. Enter executes; Tab completes; Ctrl+Space/Commands shows the list; Up/Down recalls history. Project commands still execute through the governed project backend.

Common ForgePY confirmations and text-entry prompts are embedded into the main GUI instead of secondary windows, so they cannot hide behind ForgePY. Native file/folder pickers remain OS-owned. ForgePY/Forge/ProcessHost tokens are cyan; PASS is green, WARN yellow, FAIL/ERROR red.
