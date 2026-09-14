# F977-F1000 — Forge Native GUI Takeover / Universal GUI Core

ForgePY is frozen as the compatibility/build interface. New GUI development now targets Forge Native only.

## Locked direction

- Forge Native owns all new GUI normalization.
- ForgePY remains available as the legacy build/compatibility memory and SHADOW provider while native backends migrate.
- The hybrid shell remains: command rail, navigation rail, context rail, central workspace, permanent Console/Cortex bottom rail, status strip.
- Locked shell regions visually fuse into one connected application frame instead of reading as detached rounded cards.
- Unlocking the layout restores obvious panel chrome and resizable/dockable editing affordances.
- Ctrl+Shift+L toggles layout editing/lock state.

## Bottom Console / Cortex

The bottom rail remains permanent but is no longer forced to consume a large part of the screen.

When the layout is locked:

- idle height is a compact tab/header strip;
- pointer hover animates/expands the rail to the normal working height;
- leaving the rail collapses it again;
- PIN keeps it expanded;
- Console, Cortex and Operations remain the same permanent subsystem.

When the layout is unlocked, the bottom rail returns to a normal resizable editor panel.

## Forge Remote Tool

Forge Remote is normalized as a captured in-application ForgeGUI surface rather than a foreign/native-looking utility window.

- same dark ForgeGUI theme;
- same project context;
- same foreground operation queue;
- same rounded/elevated chrome;
- captured inside the main Forge viewport;
- lock state prevents accidental movement/resizing;
- current native remote backend remains explicitly migrating until ForgeGit/GitHub Remote authority is certified.

## Universal GUI groundwork

`gui/universal.rs` introduces project-neutral GUI policy types intended to become reusable ForgeGUI core primitives:

- `DockLockMode::{Unlocked, Locked, Permanent}`
- `SurfaceDepth::{Flat, Recessed, Raised, Floating}`
- shared bottom-rail hover/peek sizing

`gui/theme.rs` now exposes reusable recessed, raised, floating and connected-shell frames plus status LED presentation.

This is the start of extracting Forge's current UI into the universal ForgeGUI core that Ember and later software can share without inheriting Forge-specific operations.

## Certification state

This tranche does not promote Forge Native out of SHADOW. Windows Cargo / Rust SHADOW remains the compile and runtime authority.
