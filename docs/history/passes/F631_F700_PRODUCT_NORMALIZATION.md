# ForgePY F631-F700 — Project UX, Self-Maintenance, Install Modes and Performance

## Dashboard
Dashboard is now the selected project's command center instead of a large read-only authority dump.
It shows project version/build, health, source, GREEN and updates; navigation to Updates, Source &
Recovery, Diagnostics, Project Tools and Advanced; identity/source context; and a Needs Attention
panel. Full Gate / Build / Test / Run remain in the contextual quick bar so they are not duplicated.

## Workspace
Workspace remains lightweight but is no longer an empty editor shell. It adds a normalized toolbar,
Save, Refresh Files, cached Quick Open filtering, an initial project overview, lazy project tree and
asynchronous read/write. Build/run/gate stay in the quick bar and execution output stays in Forge Console.

## Candidate identity
The last certified source baseline remains F60R415 until the packaged executable is certified.
The running candidate now has one explicit visible identity:
`0.5.0-candidate.700` / `FORGEPY-F700`.
Stale F449/F559 candidate labels are normalized at runtime instead of remaining visible indefinitely.

## Project version in status
The status bar project label resolves the selected project's declared version/build from
project.control.json, package.json, pyproject.toml, Cargo.toml or VERSION without recursive scanning.
ForgePY itself resolves to the current candidate identity.

## Separate ForgePY maintenance lane
Project updates and ForgePY application updates are separate authorities.
ForgePY updates are queued under the application install layout, can be staged against a copied
application image with the canonical patch engine, and are promoted as a whole-directory transaction
after the running process exits. The live executable is never patched in place.

## Install modes
Standard install:
- application: per-user program directory
- mutable ForgePY application state: LocalAppData/ForgePY
- config: Roaming AppData/ForgePY

Portable install:
- ForgePY.exe and companion files remain with a local Data folder
- `.forgepy-portable` selects portable mode

Both modes use the same separate ForgePY maintenance/update/recovery model.

## Responsiveness
The GUI no longer re-walks the entire widget tree on every Project page change.
User-facing normalization is surface-once. Duplicate project-handoff audit work from the
UnifiedWorkflow activation wrapper was removed; the existing coordinated background audit remains.
Existing async project activation, lazy Workspace indexing, scan serialization and UI-lag telemetry remain.


## Project surface lazy loading
Only the Project shell and Dashboard are built during initial shell construction. Updates,
Source & Recovery, Diagnostics, Project Tools, Advanced and compatibility pages are materialized
on first use. This removes a large amount of Tk widget construction from startup and reduces
page-switch overhead.

## Application data lifecycle
ForgePY resolves its application image independently from the selected project. After first paint,
it ensures the application state layout:
- standard: `%LOCALAPPDATA%\ForgePY` plus `%APPDATA%\ForgePY`
- portable: `<ForgePY install>\Data`

The existing user Vault/project roots remain separate from this small application-maintenance state.
