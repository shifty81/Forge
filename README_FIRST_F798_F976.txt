Forge Native cumulative overwrite F798-F976
Baseline: certified ForgePY F797 / d0c0f4afbba7046bc35026a2858696cd5f92b593
Authority: Python ForgePY remains authoritative. Rust remains SHADOW.

F976 is a compile-only repair over F975. It does not alter the hybrid-shell design.
It fixes the F975 ShellAnchor insertion that accidentally attached two derive blocks to
ShellAnchor while leaving ToolPanel without its required derives.

Expected result on Windows: cargo check should progress beyond the E0119/E0204/E0277/
E0308/E0369/E0382/E0507/E0599 trait cascade shown by the 2026-09-13 Rust SHADOW gate.

Apply by overwriting the repository root with this archive, then run the normal Rust
SHADOW gate / Full Gate. Do not promote Rust authority until Windows certification is GREEN.
