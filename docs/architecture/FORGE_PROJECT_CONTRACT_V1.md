# Forge Project Contract v1

`project.control.json` is the project-local declaration that maps a repository into Forge's universal tooling spine.

Canonical schema: `forge.project.v1`.

The project remains the authority for its own specialized commands. Forge normalizes those commands into canonical operation IDs and only falls back to generic Cargo/CMake/.NET/Gradle/Node/Python inference when no stronger project authority exists.

Minimum project block:

```json
{
  "schema": "forge.project.v1",
  "project": {
    "id": "example",
    "name": "Example",
    "kind": "rust-workspace",
    "version": "1.0.0",
    "build": "EXAMPLE-BUILD-001"
  },
  "commands": [],
  "updates": {
    "incoming": "incoming.patch",
    "patchSchema": "forge.patch.v1",
    "downloadsAutoQueue": false,
    "approvalRequiredForDownloads": true,
    "artifactAuthority": "forge",
    "lineageAuthority": "artifact-central"
  }
}
```

Canonical operation namespaces include `project.*`, `gate.*`, `build.*`, `test.*`, `run.*`, `git.*`, `source.*`, `patch.*`, `updates.*`, `doctor.*`, `diagnostics.*`, `package.*`, `assets.*`, `tooling.*`, `recovery.*`, `artifacts.*`, `dependencies.*`, and `audit.*`.

Forge may generate a candidate contract for an existing repository, but it must not overwrite a project's stronger native PCC contract without explicit project migration work.
