# Vault audit/action matrix — F11-F20

| Area | State | F11-F20 action |
|---|---|---|
| Application identity | GREEN | Vault is canonical; Forge/PCC names are compatibility shims only. |
| Project registry | GREEN | Vault-owned registry with legacy registry adoption. |
| Existing project tooling | GREEN | Scan PowerShell utilities and registered commands before inventing fallbacks. |
| Stardew toolkit | GREEN | Detect nested StardewModdingKitTools and declared actions; use existing utility. |
| Generic .NET | GREEN | Infer build/Release/full gate when a stronger tool is absent. |
| Root-drop patch intake | GREEN | Same hash-verified Vault queue as Downloads. |
| Downloads intake | GREEN | Background watcher + explicit Scan Intake. |
| Universal patch mutation | GREEN | Transactional apply, preimage checks, atomic replace, rollback, receipts. |
| Source self-update | GREEN (source mode) | Patch own source and request/relaunch restart. |
| Packaged EXE swap | DEFER | Requires dedicated bootstrap/updater once Vault is frozen into an executable. |
| Vault project scan | GREEN | Files, assets, source, JSON, duplicates, large files, hashes, environment, commands/capabilities. |
| Git/GitHub/Forgejo visibility | GREEN | Status/remote visibility retained. |
| Git/GitHub/Forgejo write authority | NEXT | Continue absorbing GREEN-gated commit/push and Forgejo lifecycle from strongest donors. |
| Cortex machine API | NEXT | Expose the same command/scan/intake spine as structured JSON/JSONL tools. |
| Debug bundles | NEXT | Generalize automatic failure bundle generation for arbitrary registered projects. |
| Composite/nested project graph | NEXT | Promote child project discovery from scan evidence into first-class registry graph. |
| Filesystem watching/index refresh | NEXT | Incremental catalog refresh rather than full rescans for every change. |
| Content provenance/licenses | NEXT | Extend Library record model beyond patch provenance into reusable assets/dependencies. |
