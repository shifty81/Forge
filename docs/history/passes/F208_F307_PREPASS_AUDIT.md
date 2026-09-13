# ForgePY Whole-Project Audit — F60R167 Baseline Before F208–F307

Baseline audited: `0.4.167-F60R167 / FORGEPY-F60R167`.

## What was genuinely strong

- Universal project discovery/PCC adoption, build/run/gate routing and project-local authority.
- Transactional `forge.patch.v1` handling, approval, Patch Lineage and rollback.
- Patch-only automatic movement safety introduced in F60R63.
- ForgeGit + GitHub source-control foundation.
- Vault D: catalog, classification and project ownership foundations.
- Activated tool registry, generated adapters and Toolchain Doctor foundations.
- Artifact Central, project health, debug evidence and package manifests.
- F60R67 startup/Tk lifecycle protections remained intact in the F60R167 package.
- GUI visual identity had already converged on the desired dark/cyan three-panel family.

## Major gaps found

### 1. Many F108–F207 modules were models, not integrated services
Activity, receipts, provenance, state broker, command bus, job queue, plugin registry,
project graph, backups, release, retention, automation and certification existed but
many had zero runtime importers. The architecture was present but disconnected.

### 2. Worker architecture remained fragmented
ForgeGUI still owned many direct threads. The worker/event architecture existed but
was not yet the universal lifecycle authority.

### 3. Tool activation stopped short of a governed runtime
Tools could become READY/VERIFIED, but typed parameters, output bounds, receipts,
cancellation, timeout governance and project-confinement were not consistently applied
through the visible Tooling UI.

### 4. Plugins were registry-only
There was no runtime loader, no enabled+approved gate and no command-bus registration path.

### 5. Adapter model was write-only
Generated adapters existed, but ForgePY lacked a registry/resolver that could rank and
consume machine-local adapters by project identity/kind.

### 6. Vault/Artifact intelligence remained thin
Search existed, but classification facets, duplicate groups, ownership confidence and
stale Artifact Central cleanup were not first-class services.

### 7. Backup/recovery was planning-only
Backup and restore modules returned plans; there was no explicit verified backup creator.

### 8. Release pipeline was largely data-model only
Release manifests existed, but offline bundle assembly and signing-readiness truthfulness
were not implemented as reusable services.

### 9. Settings validation was shallow
Critical invariants such as forbidding automatic non-patch archival were not enforced by
the schema layer.

### 10. First-run and standalone build paths needed stronger truth boundaries
The system had plans for first-run and Nuitka packaging, but no explicit invariants stating
that dependency installation and non-patch movement remain operator-controlled.

### 11. Activity scaling
Activity read the entire JSONL ledger on every recent-history query.

### 12. Windows-host boundary remains real
A Linux/static gate cannot certify Tk/Win32 lifecycle, Defender/SmartScreen, raw tray code,
Nuitka one-file behavior or self-replacing executable handoff.

## F208–F307 objective

Close the disconnected-service gap: make the existing architecture actually participate in
runtime operations, deepen tool/plugin/adapter governance, strengthen Vault/source/recovery/
release services, reduce GUI-owned background responsibility and prepare a truthful Windows
certification handoff without changing the established visual language.
