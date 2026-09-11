# One-time bootstrap from ProjectControlCenter-Standalone 0.10.2

The old 0.10.2 package cannot consume its own replacement because it predates Vault's universal update engine. This is the only manual overwrite required.

1. Close the old Project Control Center GUI.
2. Extract the contents of `Vault_0.2.0-F11-F20_Bootstrap_Overlay.zip` directly into the existing `ProjectControlCenter-Standalone` folder and allow overwrites.
3. Start `Vault.vbs` (the old `ProjectControlCenter.vbs` alias also launches Vault after the overwrite).
4. Confirm the header shows `VAULT` and `v0.2.0-F11-F20 ACTIVE`.
5. Register/select the Vault application folder if it is not already active.
6. Test self-update by dropping `Vault_SelfUpdate_Test_0.2.1.zip` either into the Vault application root or Downloads.
7. Click **APPLY UPDATES** (or run Build/Full Gate). Vault should apply the patch transactionally and ask to restart.
8. After restart, the header/self-test reports `0.2.1-F11-F20`.

The test update is not a fake watcher-only test: it modifies `app/VaultVersion.py` through the same universal transaction engine and verifies an exact preimage SHA-256 before replacement.
