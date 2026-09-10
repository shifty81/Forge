# D: Drive Portability

On Windows with a D: drive present, a fresh Vault configuration defaults to:

```text
D:\Vault       durable Vault state/catalog/intake/Forgejo/recovery
D:\Projects    preferred portable project root
D:\            initial drive/project scan root
```

The application source itself can live anywhere. Vault's durable state is no longer required to live beside the application checkout.

## Moving an existing Vault

Use **Vault > Storage / Portable Locations > Move Vault Home**. Vault copies to the selected target, verifies each copied file by SHA-256, updates settings, writes a migration receipt under `recovery/storage-migrations`, and retains the old source location. Deletion of the old location is intentionally not automatic.

## Moving an active project

Use **Vault > Storage / Portable Locations > Migrate Active Project** after setting **Projects Root** (normally `D:\Projects`). Vault copies the complete project into a staging directory on the destination volume, verifies every regular file by SHA-256, atomically promotes the verified copy, preserves the existing registry identity, switches the active project to the new portable root, writes a project-migration receipt, and retains the old project as rollback evidence.

Projects already under the configured Projects Root gain a registry `portablePath`. If Projects Root is later changed and the old absolute path no longer exists, Vault can resolve the same relative path under the new Projects Root. **Scan D Drive** and **Register Scanned** can rebuild the project registry from disk and preserve nested/composite project relationships.

Vault does not silently rewrite arbitrary absolute paths embedded inside third-party project files. Project-specific build/gate tooling should certify the migrated copy before the old source is removed in a later explicit cleanup operation.
