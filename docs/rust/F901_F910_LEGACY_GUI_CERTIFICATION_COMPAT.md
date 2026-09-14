# Forge Native F901-F910 — Legacy GUI Certification Compatibility

Baseline: cumulative F798-F900 modular ToolPanel lane over certified ForgePY F797.

The first Windows Full Gate of the F900 panel-native tranche proved the new F798-F900 tests but exposed historical GUI source-shape probes from F755-F787. Those failures were compatibility regressions, not evidence that the ToolPanel architecture should be reverted.

## Repair strategy

F901-F910 preserves the modular panel graph and restores the older certification contracts as typed compatibility views:

- `ProjectSection` is reintroduced as a compatibility enum that maps one-to-one to `ToolPanel` project destinations.
- persisted shell state keeps `active_project_section` and `project_rail_collapsed` so older readers/tests remain valid; the flags now affect the modular Project Navigator itself.
- Project Navigator iterates `ProjectSection::ALL`, hides Project Tools when no internal PCC exists, and dispatches through the panel graph.
- the former `forge-native-project-context-rail` identifier becomes a stable egui ID on the Project Navigator ToolPanel, not hard-coded shell chrome.
- the selected project icon is rendered through `widgets::project_icon_uri` inside Project Navigator.
- the Project Health tool exposes the historical `FORGEPY HEALTH` mirror label while retaining its standalone/tool identity.
- `Reset ForgePY Layout` now explicitly reloads the built-in locked ForgePY Mirror interface.
- panel search retains the historical `Search widgets…` vocabulary while searching the new ToolPanel registry.
- ForgeDock keeps the historical `find_tab(&tab)`/deduplication contract and the Mirror preset retains a root `split_right(NodeIndex::root()` construction.

No fixed shell regions were restored. All 27 Forge surfaces remain reusable nestable ToolPanels and continue to support the shared docked/standalone renderer.

## Certification boundary

Python structural compatibility tests can be run before Windows Cargo availability. Rust compile/runtime certification remains a Windows Rust SHADOW/Full Gate responsibility. Native takeover remains false.

## Cargo repair observed in the same Windows gate

The uploaded gate also exposed Rust E0308 in `ForgePanelViewer::ui`: the fallback match arm returned `egui::Response` while the typed panel arms returned `()`. F910 wraps the fallback label in a block with a terminating semicolon so every match arm returns unit.
