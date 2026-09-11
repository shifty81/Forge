# ForgePY Module Authority

ForgePY is the product and public application authority. New ForgePY-owned code should import the canonical `ForgePY*` surfaces where one exists. Historical `Vault*`, `Forge*`, and `PCC*` implementation modules remain available as compatibility providers because project contracts, older patches, and persisted state may still refer to them.

Current canonical facades include `ForgePYSettings`, `ForgePYPaths`, `ForgePYIntake`, `ForgePYPatchEngine`, `ForgePYSourceControl`, `ForgePYHealth`, `ForgePYTray`, `ForgePYBrand`, `ForgePYVersion`, `ForgePYStandalone`, and `ForgePYGate`.

This is a staged normalization: implementation modules are only renamed when doing so cannot invalidate project adapters or historical patch preimages. Visible product surfaces must say ForgePY; Vault is the storage/artifact subsystem; PCC is the project-owned CLI/control contract.
