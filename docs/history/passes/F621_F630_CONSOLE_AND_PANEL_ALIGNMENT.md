# ForgePY F621-F630 — Forge Console + Panel Alignment

## Console identity

The persistent embedded right-side console is now **Forge Console**.

It is a ForgePY-owned execution/output surface and remains visible alongside the major
application surfaces. It is not the same thing as a project's own CLI.

**Project CLI** is the explicit action that opens the selected project's own CLI/PCC surface.
On Project and Workspace quick bars, Project CLI is pinned to the absolute far-right edge.

## Geometry authority

The global content/console PanedWindow is the shared alignment authority.

Normal page insets:
- horizontal: 8 px
- vertical: 6 px

Forge Console:
- header horizontal inset: 8 px
- header top inset: 6 px
- body horizontal inset: 8 px
- command-row horizontal inset: 8 px
- bottom inset: 6 px

Project Workspace previously had:
- an extra 6 px outer inset around its internal split pane;
- a 13 x 12 px center-content inset.

That caused its panel borders and content header to sit inward/lower than Forge Console.
F630 removes the duplicate Project outer gutter and normalizes Project center content to 8 x 6.

Vault, Workspace and Settings top-level shells are normalized to the same 8 x 6 content inset.
The policy reruns after lazy page builds and on debounced window resize, preventing individual
legacy page builders from reintroducing misalignment.
