# Forge Native F851-F900 — Modular Tool Host + Panel Polish

Baseline: certified ForgePY `FORGEPY-F797`, cumulative with F798-F850.

## Direction lock

Forge is a **tool platform**, not a collection of pages. Every user-facing Forge capability is a
`ToolPanel` with a stable identity and enough metadata to be hosted in multiple ways without
rewriting its UI or backend binding.

The same panel renderer is now consumed by:

1. the nested `ForgeDock` interface graph;
2. the locked **ForgePY Mirror** preset;
3. user-saved custom interfaces;
4. a standalone native tool host launched with `ForgeNative --tool <panel-id>`;
5. the convenience `ForgeTool` binary.

This means a panel can feel like a small focused application while remaining part of one cohesive Forge product.

## Stable tool registry

All 27 current panels have a `PanelDescriptor` containing:

- stable kebab-case tool id;
- title/category/summary;
- global/project/workspace/system scope;
- native/hybrid/shadow maturity;
- preferred standalone window size;
- minimum standalone window size;
- singleton policy;
- standalone-host capability.

The Tool Library searches this metadata rather than maintaining another hard-coded panel list.

## Shared tool chrome

Every hosted panel receives the same compact tool header:

- icon + tool name;
- category;
- current maturity badge;
- host mode (`DOCKED` / `STANDALONE`);
- stable tool id + one-line purpose;
- Refresh action;
- Open Standalone action when running inside the main interface.

The panel body underneath remains the exact same implementation used by the normal Forge workflow.

## Standalone tool mode

`ForgeNative` now accepts:

```text
ForgeNative --root <project-root> --tool <tool-id>
```

Examples:

```text
ForgeNative --root C:\Projects\Havenwild --tool diagnostics
ForgeNative --root C:\Projects\Havenwild --tool forge-console
ForgeNative --root C:\Projects\Havenwild --tool patch-intake
```

A second Cargo binary target, `ForgeTool`, provides the same focused-host behavior directly.
It defaults to `overview` when `--tool` is omitted.

Standalone tools retain the same:

- selected project/root;
- operation queue;
- console/service bindings;
- project census/toolchain context;
- panel renderer;
- Forge theme and sizing metadata.

Panel-to-panel navigation inside a standalone host changes the focused tool rather than creating a competing application architecture.

## ForgePY Mirror remains a preset

Nothing in this pass removes the current ForgePY parity layout. `ForgePY Mirror` remains the default
locked preset. The difference is that each visual region is now demonstrably reusable as a focused tool.

## Polish

F851-F900 also standardizes:

- searchable card-style Tool Library entries;
- maturity badges;
- stable tool IDs exposed in UI/context menus;
- contextual Open Standalone/Refresh actions;
- project-bound standalone launch arguments;
- preferred/minimum window geometry per tool;
- visible registered-tool count in the interface bar;
- the existing rounded dark Forge visual language across both hosts.

## Certification boundary

This source is intentionally still `SHADOW`. The container used to author this tranche has no Rust
compiler, so Windows `cargo check/test`, Rust SHADOW gate, and an interactive standalone-tool soak remain
required before advancing native identity or authority.

The next backend tranches should migrate functionality **behind these stable tools**, beginning with
Vault/Explorer/catalog, ForgeGit/GitHub, governed Patch Intake, Internal PCC Provider execution and
Workspace file services. The interface/tool-host architecture should not need another rewrite.
