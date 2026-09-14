# Forge Native F798-F950 Rust Source Handoff

This is the cumulative **changed/new Rust-lane handoff over certified F797**, not a replacement for the entire Forge repository. Unchanged F797 modules remain supplied by the certified repository.

The handoff is cumulative through F950 and includes the panel-native interface system, standalone tool host, native self-update foundation, F910 legacy GUI certification compatibility, and the F950 Tooling / CLI workbench.

## F950

The new Tooling workbench deliberately keeps the 27-panel registry stable. Existing panels are reorganized into a usable CLI/tooling interface:

- `Project Tools`: command catalog/search/favorites/availability
- `Project CLI`: selected command inspector + safe registered alias runner
- `Operations`: active queue/pending cancellation/last result/history
- `Forge Console`: raw transcript/debug output
- `Project Context`, `Diagnostics`, and `Quick Actions`: contextual support

All execution still flows through the existing project-bound foreground queue/provider path. Detected Cargo/CMake/.NET/etc. operations are displayed as project-intelligence evidence and are not executed as arbitrary shell commands.

Native identity intentionally remains F797 SHADOW until Windows certification passes.
