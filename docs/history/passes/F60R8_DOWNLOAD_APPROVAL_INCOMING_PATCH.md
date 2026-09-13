# Forge F60R8 — Downloads approval and `incoming.patch`

Forge keeps Downloads as a discovery/catalog surface, never an execution authority. A completed patch package discovered in Downloads is moved into the matching project's Artifact Central `patches/available` area and remains `AVAILABLE` until a user explicitly approves it.

## User workflow

1. Download a Forge patch package normally.
2. Forge's intake watcher scans immediately at startup and periodically thereafter.
3. The package is hash/date/project/build verified and cataloged as `AVAILABLE`.
4. Forge logs and, when enabled, sends a tray notification when an AVAILABLE package is compatible with the active project.
5. Use **Updates > Approve Download…** to select and authorize a compatible package. Approval re-checks SHA-256 and live project/build/source preconditions and writes a durable approval receipt.
6. Use **Apply Validated Queue**, or use **Apply Updates** with no existing queue and Forge will offer the compatible downloaded package for explicit approval before applying it.

Downloads packages never auto-queue and never auto-apply.

## Reserved single-file root intake

Every project may use one reserved root transport name:

`incoming.patch`

`incoming.patch` is a ZIP-compatible Forge patch container. It must contain a top-level `PATCH_MANIFEST.json`. The root-drop is itself the explicit user trust action, so a valid matching `incoming.patch` is ingested into the project's queue, removed from the root after durable archival, staged as a ZIP-compatible internal transport (`updates/inbox/incoming.zip`) for compatibility with existing project-native PCC engines, and applied through the normal transaction path.

Forge continues to accept legacy/root patch `.zip` transports for compatibility, but `incoming.patch` is the normalized front door going forward.

## Approval evidence

The intake catalog stores `approved_utc` and `approved_root`. A Downloads-origin item in `QUEUED` or `STAGED` state is considered executable only when explicit approval evidence is present. Older Downloads queue rows without approval are still demoted to `AVAILABLE` by the F60R2 safety guard.

Approval receipts use schema `forge.patch.approval.v1` and are stored under the project's Artifact Central `patches/receipts` area.
