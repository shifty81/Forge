# F951-F975 — Hybrid Shell and Permanent Console/Cortex Rail

## Decision

F900-F950 proved the ToolPanel and standalone-host architecture, but allowing every structural surface to participate in the live dock graph made the normal Forge application visually incoherent. F951-F975 keeps the modular ToolPanel implementation while restoring a small, explicit application shell.

## Permanent shell anchors

The normal Forge host now owns five structural anchors:

1. **Top Command Rail** — project identity, Full Gate, Build, Test, Run, Refresh, Project CLI, Tooling preset, interface selector, panel library and lock state.
2. **Left Navigation Rail** — Forge navigation plus selected-project navigation.
3. **Right Context Rail** — tabbed Project Health, Patch Intake, Project Context and Recent Activity.
4. **Bottom Forge Console / Cortex Rail** — permanent resizable rail with Console, Cortex and Operations modes.
5. **Status Rail** — compact project/interface/version state.

The center remains a normal ForgeDock workspace for authoring/operations tools.

## Console/Cortex authority

Forge Console is no longer allowed to disappear from the normal host. Requests to open Forge Console focus the permanent bottom rail. Operation Queue requests select the Operations mode in the same rail.

Cortex receives a permanent embedded host surface inside this rail. F975 intentionally marks the Cortex native transport as SHADOW: the location and UI host are real, but no native Cortex backend connection is claimed until the adapter/IPC lane is certified.

## Structural ToolPanels remain reusable

ForgeNavigator, ProjectNavigator, QuickActions, ProjectHealth, PatchIntake, ProjectContext, RecentActivity, ForgeConsole, OperationQueue and Status retain their stable ToolPanel identities and standalone-host capability. In the normal Forge host, `ToolPanel::shell_anchor()` routes them to permanent rails instead of creating duplicate center tabs.

## Workspace behavior

`ForgeDock::open_or_focus()` rejects shell-anchor panels. Built-in presets now describe the center workspace only. Custom interfaces also persist only the center DockState. Storage keys were advanced to the hybrid-shell generation so old all-detached layouts cannot resurrect.

## Compatibility

Historical F755-F950 source-shape probes remain represented for cumulative certification without restoring the old runtime geometry. The 27-panel registry and standalone tool host remain intact.

## Certification in producer environment

Python structural suites:

- native self-update foundation
- panel/interface parity lock
- F851-F900 modular tools
- F901-F910 legacy GUI compatibility
- F911-F950 tooling workbench
- F951-F975 hybrid shell

Result: **42/42 PASS**.

Cargo/rustc are not available in the producer environment. Windows Full Gate remains the compile/runtime authority.
