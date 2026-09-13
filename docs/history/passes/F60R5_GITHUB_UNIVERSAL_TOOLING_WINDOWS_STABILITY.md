# Forge F60R5 — GitHub onboarding, universal tooling, Windows stability

## Authority order

1. Project-declared `project.control.json`.
2. Project-native machine provider.
3. Project command registry (`ProjectCommandRegistry.ps1` + a `-Command` host).
4. Explicit PowerShell `-Action` tooling.
5. Conservative build-marker fallback (Cargo, Gradle, .NET, Node, CMake, Python).

Forge does not replace a stronger project PCC merely because it can recognize the language.

## GitHub onboarding

The Projects workspace supports local registration and GitHub cloning into the configured Projects Root. GitHub remotes are persisted into Forge's registry/passport and can be opened in the default browser. Source Control remains ordinary non-force Git.

## Windows process policy

Periodic read/status probes use `CREATE_NO_WINDOW` and hidden startup info. The active health scheduler allows at most one outstanding health scan. Long-running project operations remain embedded in Forge's captured console lifecycle.

## Cross-volume Artifact Central

A verified transport can originate on C: while Artifact Central lives on D:. Forge copies to a temporary file beside the final destination, verifies SHA-256, atomically promotes within D:, verifies the final file, then removes the source.

## Havenwild

Forge detects the mature Havenwild-style `HavenwildTools.ps1` + `ProjectCommandRegistry.ps1` contract and creates canonical `gate.full`/`build.native` aliases that dispatch back to the existing project PCC rather than generic Cargo inference.
