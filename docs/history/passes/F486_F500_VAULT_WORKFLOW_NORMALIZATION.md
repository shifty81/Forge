# ForgePY F486-F500 — Vault Workflow Normalization

This block is cumulative with F450-F485.

## User-facing shell

The primary left rail is now exactly:

1. Vault
2. Project
3. Workspace
4. Settings

Legacy/duplicate top-level `Operations`, `Updates`, `Projects`, `Source Control`,
`Dashboard`, and `Cortex` entries are hidden from the primary rail.

## Vault is the application home

ForgePY startup still invokes the legacy `Projects` route internally for compatibility,
but the route now renders as the **Vault Projects** home and the visible active tab is Vault.

Vault Projects is the normal workflow:

1. Add Local Project or Clone GitHub.
2. Select a project.
3. Audit / standardize it.
4. Open Project.
5. Continue project-specific work in Project Dashboard.

The project table remains the existing mature registered-project table rather than inventing
another project registry UI.

## Advanced Vault Library

The prior whole-drive Vault Catalog has not been deleted. It is now accessed with **Library**
from the Vault quick bar. It is intentionally treated as advanced catalog/lineage inspection,
not the startup workflow.

Library quick actions are limited to:

- Projects
- Scan Library
- Refresh

## Duplication removal

- Project add/clone/open buttons are owned by the contextual Vault quick bar.
- Duplicate toolbar copies on the legacy Projects page are hidden.
- Patch Select remains in the right-hand Patch Intake rail; it is no longer duplicated in the Vault quick bar.
- Project update application remains under Project / Updates and Project Dashboard.
- Source-control operations remain project context, not a separate top-level workspace.

## Contextual quick bar

### Vault / Projects
`ADD PROJECT | CLONE GITHUB | OPEN PROJECT | AUDIT | LIBRARY | REFRESH`

### Vault / Library
`PROJECTS | SCAN LIBRARY | REFRESH`

### Project
`FULL GATE | BUILD | TEST* | RUN | APPLY UPDATES | PROJECT CLI | REFRESH`

### Workspace
`BUILD | RUN | FULL GATE | PROJECT CLI | REFRESH`

`*` only when the active project exposes a real test capability.

## Project selection

Double-clicking a project now means **Open Project**:
- activate the selected project;
- open its Project Dashboard;
- select Project in the left navigation;
- refresh the contextual quick bar.

## Audit

Vault Audit refreshes:
- Project Audit JSON;
- ForgePY Support Handoff;
- Project Integration Handoff;
- Project Intelligence snapshot.

No project source is modified by an audit.
