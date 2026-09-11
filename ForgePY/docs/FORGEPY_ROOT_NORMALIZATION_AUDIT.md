# ForgePY Root Normalization Audit — F60R12

## Result

The previous package had three overlapping identities at its root: `ProjectControlCenter-Standalone`, `Forge`, and `Vault`. The runtime had already moved toward Forge authority, but packaging, launchers, documentation, historical release ZIPs, and compatibility scripts still made the root look like a renamed PCC bundle. F60R12 makes `ForgePY` the single product/root authority without deleting the project-PCC contract or Vault subsystem concepts.

## Action matrix

| Area | Previous state | F60R12 action | Authority after normalization |
|---|---|---|---|
| Package folder | `ProjectControlCenter-Standalone/` | RENAME | `ForgePY/` |
| GUI launcher | `Forge.vbs` | RENAME + compatibility shim | `ForgePY.vbs` |
| CMD launcher | `Forge.cmd` | RENAME + compatibility shim | `ForgePY.cmd` |
| Console launcher | `ForgeConsole.cmd` | RENAME + compatibility shim | `ForgePYConsole.cmd` |
| Verification | `VerifyForge.cmd` plus PCC/Vault variants | COLLAPSE | `VerifyForgePY.cmd` |
| Version authority | `ForgeVersion.py` / product `Forge` | REWRITE | `ForgePYVersion.py` / product `ForgePY` |
| Standalone entrypoint | `ForgeStandalone.py` | ADD canonical wrapper | `ForgePYStandalone.py` |
| Package manifest | `FORGE_PACKAGE_MANIFEST.json` | RENAME | `FORGEPY_PACKAGE_MANIFEST.json` |
| Root PCC launchers | visible at root | MOVE | `compat/legacy-launchers/` |
| Root Vault launchers | visible at root | MOVE | `compat/legacy-launchers/` |
| Historical update kits | visible at root | MOVE | `archive/releases/` |
| Old standalone docs | visible at root | MOVE | `docs/history/` |
| Project ID | `forge-project-control-center` | RENAME | `forgepy` |
| Visible UI branding | mixed `Forge`, `Vault`, PCC | NORMALIZE | `ForgePY` |
| Vault term | sometimes application identity | KEEP only as subsystem/workspace | Vault storage/artifact workspace |
| PCC term | sometimes application identity | KEEP only as project contract terminology | project-local CLI/PCC spine |
| Patch schemas | `forge.patch.v1` | KEEP | compatibility contract; changing it would break projects |
| Environment variables | `FORGE_*`, `VAULT_*` | EXTEND | `FORGEPY_*` preferred where touched; old names remain readable |

## Deliberately not renamed

The `forge.project.v1` / `forge.patch.v1` schemas and project-side PCC discovery terminology remain stable because they are interoperability contracts, not visible product branding. Forgejo also keeps its proper upstream name. Internal legacy Python module names remain supported so existing project adapters and old patches can continue importing them while ForgePY-specific canonical entrypoints are introduced.

## Root cleanliness rule

New release ZIPs should have one top-level folder named `ForgePY`. Historical bundles, update kits, and retired launchers do not belong in that folder's top-level operational surface. Only canonical ForgePY launchers, the compatibility `Forge.*` aliases, the project contract, package manifest, README/changelog, requirements, and normal source directories should be visible there.
