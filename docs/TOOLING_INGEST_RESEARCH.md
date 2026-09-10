# Vault Tooling Ingest Research

Vault should treat existing project automation as donor capability and build a universal inventory around it instead of rewriting each script.

## Verified project families

### Havenwild

The repository has a formal tool registry plus organized build, control, automation, validation, repair and archive areas. The registry exposes active Python/PowerShell/CMD tooling for asset intake/cataloging, LPC/character pipelines, terrain generation/audits, packaging/source rollups, release staging, reports/build attestations and validation. Vault should ingest the registry directly as a high-confidence source.

### Cortex

Cortex carries root-control/PCC tooling and a `tools/control` + `tools/pcc` split. Vault should expose Cortex as a first-class workspace/client while retaining Cortex's own independent application/service boundary.

### Ember

Ember carries root PCC/Forge compatibility launchers, project contracts, certification/config surfaces and a project-local patch/bootstrap system. These are useful donors for root-drop update semantics and machine-readable project operations.

### Codename Subspace

Subspace exposes control, dependency, PCG, smoke, validation and Blender tooling. Its Blender area includes NovaForge generation, PCG export, Shipyard automation and audit/normalization scripts. Vault should classify these as Blender/Asset Pipeline/PCG domains and invoke them through the Blender CLI adapter rather than treating them as arbitrary Python files.

### Stardew Modding Kit

The kit exposes `StardewModdingKitTools.cmd`, bootstrap/environment authority, `project.control.json`, `project.bootstrap.json`, and project tooling. Vault should prefer these declared project operations over generic `.NET` inference.

### Other historical projects

Searches across the user's repositories also surface Blender bridges/add-ons, Atlas/AI tool registries, external-tool bridges, root control centers, server/remote execution components and project contracts. These should feed the same universal Tool Index when the corresponding project is registered or scanned locally.

## Tool classification

Vault's scanner recognizes Python, PowerShell modules/scripts, CMD/BAT, shell, JavaScript/TypeScript, Lua, Ruby, Perl, C# script and Groovy. It classifies likely purpose without executing the file:

- control / root operations
- build
- validation / quality gate
- tests / smoke
- patch / update
- source control
- packaging / release
- dependency/bootstrap
- assets / import/export
- Blender
- character
- terrain/world
- PCG
- editor
- server/deploy
- automation

## CLI inventory

Vault also records availability of Git, gh, Forgejo, Python, PowerShell, Cargo/Rust, CMake/Ninja/MSBuild, .NET, Java/Gradle, Node/npm, Blender, ffmpeg, 7-Zip, SQLite, ripgrep, Docker and related build tools.

The long-term rule is: **discover -> classify -> bind to a typed command -> run through the Vault operation host**. Discovery alone never grants execution authority.
