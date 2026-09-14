# Forge Native F826-F850 — Panel-Native Interface Parity

Baseline: certified ForgePY `FORGEPY-F797`, cumulative with F798-F825.

## Correction to the F825 lock

F825 correctly identified the current ForgePY visual roles, but made too much of that geometry immutable.
The final target is more flexible:

- the **panel graph is the interface authority**;
- every ForgePY workflow surface is a reusable native Rust `ToolPanel`;
- panels can be tabbed, split, nested, moved, closed and reopened while an interface is editable;
- the assembled graph can be saved as a named interface;
- an interface can be locked so normal operation cannot accidentally rearrange it;
- the current ForgePY arrangement survives as the built-in **ForgePY Mirror** preset.

The mirror is therefore a preset, not a second GUI architecture.

## ToolPanel registry

The F850 native registry contains 27 first-class panels:

### Interface
- Forge Navigator
- Quick Actions
- Interfaces
- Status

### Project
- Project Navigator
- Overview
- Source
- Build & Test
- Run
- Updates
- Recovery
- Diagnostics
- Artifacts
- Project Tools
- Project CLI
- Intelligence
- Native Migration
- Asset Dependencies
- Project Health
- Patch Intake
- Project Context
- Recent Activity

### Operations
- Forge Console
- Operations

### Workspace
- Vault
- Workspace

### System
- Settings

Existing F797 native pages are delegated through the same `ForgeTabViewer`; F826-F850 wraps them in the unified `ToolPanel` graph instead of duplicating their implementation.

## ForgePY Mirror preset

The `LayoutPreset::Forge` user-facing label is now **ForgePY Mirror**.

It composes the current ForgePY visual language from panels:

`Forge Navigator | Project Navigator | Quick Actions + Workbench | Forge Console | Project Health/Patch Intake/Project Context/Recent | Status`

The center workbench contains the project capability panels as tabs so locked navigation can focus existing panels without changing the layout.
The preset defaults to locked.

## Other built-in presets

The exact same panels can be recomposed into:

- Development
- Operations
- Intelligence
- Minimal

These are not separate implementations. They are different `DockState<ToolPanel>` graphs over the same services and panel renderers.

## Custom interfaces

`InterfaceLibrary` persists named custom interfaces containing:

- interface name;
- complete nested `DockState<ToolPanel>`;
- lock state.

The Panels & Interfaces palette can:

- search/reopen any registered panel;
- load built-in presets;
- save/update the current graph as a named interface;
- load/delete saved custom interfaces;
- lock/unlock the active interface.

## Lock semantics

When locked the host disables:

- tab close buttons;
- tab dragging;
- tab context menus;
- leaf collapse controls;
- expanded separator grab width/drag highlighting.

This preserves the selected interface during normal operation. Unlocking re-enables layout authoring.

## Parity boundary

This tranche establishes **UI topology parity**, not backend takeover.
Panels that still call the Python/PCC bridge remain marked `PYTHON_SHADOW`/`MIGRATING` in `native/forge-rs/parity/gui-parity.json`.

Major backend blockers remain:

1. native SQLite/WAL Vault catalog + Explorer-like browser;
2. native governed patch intake/classification/application;
3. native Internal PCC Provider execution;
4. native ForgeGit + GitHub Remote authority;
5. native Workspace file browser/editor services;
6. installed/portable self-update lifecycle certification.

No Rust authority phase is advanced by this source overlay until the Windows Rust SHADOW gate compiles and certifies it.
