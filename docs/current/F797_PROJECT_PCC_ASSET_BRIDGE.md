# F797 Project PCC / Vault Asset Authority Bridge

ForgePY now treats mature project-owned control centers as authoritative providers rather than forcing them through a generic Python interpretation. PowerShell PCCs route through normalized `project.control.json` commands, and the project launcher remains available as a first-class Project Tools action.

## Root-drop interoperability

If a project declares both patch authority (`patch.apply`) and recovery authority (`recovery.undo-last`, rollback, or equivalent), ForgePY preserves root/inbox patch transports exactly where the project PCC expects them. Direct internal PCC launch and ForgePY `Apply Updates` therefore operate on the same transport bytes. Forge does not silently convert or weaken the project's patch format. Manual patch selection may return `PROJECT_NATIVE_REVIEW` when Forge universal preconditions do not match but the internal PCC can perform its own guarded compatibility decision.

## Asset requirements and recovery

Projects may declare `forge.assets.json` (or equivalent supported location) with hash-bound source requirements. Before Full Gate, ForgePY can hydrate an exact missing source from Artifact Central, the Vault drive catalog, or a verified `FORGEPY_BACKUP_MANIFEST.json` archive. Automatic hydration requires an authoritative SHA-256 and exactly one matching source. Ambiguous or unbound sources fail closed.

If a project does not yet declare asset requirements, failed Full Gate diagnostics scan only recent project logs for asset filenames and correlate them against Vault/backup catalogs. This path is advisory: inferred log evidence never causes automatic source replacement.

Example:

```json
{
  "schema": "forge.assets.v1",
  "assets": [
    {
      "id": "various_planets_v1",
      "name": "various_planets.glb",
      "sha256": "<certified source sha256>",
      "destination": "various_planets.glb",
      "required": true,
      "license": "CC-BY-4.0"
    }
  ]
}
```

The individual project remains responsible for transforming that immutable source into its derived runtime content. ForgePY owns durable discovery, hash/provenance matching, recovery source selection, and hydration evidence.
