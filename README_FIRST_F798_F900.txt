Forge Native cumulative overwrite F798-F900

Baseline: certified ForgePY FORGEPY-F797.
Supersedes F798-F807, F798-F825 and F798-F850 handoffs.

This cumulative source adds native self-update foundations, panel-native interfaces,
ForgePY Mirror, named/lockable nested layouts, the 27-tool descriptor registry, shared
docked/standalone rendering, and ForgeNative/ForgeTool standalone tool hosting.

Apply over the F797 repository root, overwrite files, then run the normal internal PCC
Full Gate / Rust SHADOW gate before considering the Rust lane certified.
