# Cortex Project-Side PCC Reference Snapshot

This folder is a recovery/reference copy for the Cortex repository's project-side Project Control Center authority.

It is **not** the portable app entrypoint. Use the package-root `ProjectControlCenter.vbs` for normal standalone operation.

Reference components:

- `PROJECT_CONTROL_CENTER.cmd`
- `project.control.json`
- `tools/control/CortexPCC.py`
- `tools/control/CortexPCCConsole.py`
- `tools/control/CortexPCCMaintenance.py`
- `tools/control/CortexGitAuthority.py`
- `tools/control/CortexPatchAuthority.py`

The portable universal files that complement this project-side set are under the package `app/` directory, including the current GUI, discovery, auto-adapter, operation-host, repo-hygiene, Vault catalog, and surface-common modules.

This snapshot is intended for comparison/recovery. Normal project registration does not copy these files into a project.
