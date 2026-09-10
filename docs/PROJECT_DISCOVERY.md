# Vault project/tool discovery

Vault treats project-side tooling as an authority donor rather than requiring every project to be rewritten.

Discovery order:

1. `project.control.json` when present.
2. Declared Python machine provider when present.
3. Existing PowerShell control/tool utilities, including `tools/control/*Tools.ps1` and `tools/control/*.ps1`.
4. Standard build markers for Rust, Gradle, .NET, Node, Python and existing CMake build trees.
5. Generated read-only status/health operations.

PowerShell utilities are inspected for actions explicitly declared in a `ValidateSet`, `switch ($Action)` cases, or `$Action -eq '...'` comparisons. Recognized actions map into stable Vault operations; every other declared action remains available under Advanced Commands. A menu-only utility is exposed as `run.project-tools` instead of being silently ignored.

Stardew-specific recognition includes SMAPI `manifest.json`, shallow mod manifests and `tools/control/StardewModdingKitTools.ps1`. A toolkit can therefore retain its existing environment/SMAPI/rehydration logic while Vault becomes the common operator surface.
