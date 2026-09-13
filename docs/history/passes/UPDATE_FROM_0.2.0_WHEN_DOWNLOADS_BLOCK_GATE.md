# Updating Vault 0.2.0 when Downloads blocks Full Gate

Vault 0.2.0-F11-F20 can treat malformed patch-like ZIPs in Downloads as a blocking intake failure before it reaches a root-dropped self-update. F21-F40 repairs that coupling, but the running old process must first be allowed to consume the repair patch.

## Recovery update sequence

1. Close the current Vault window.
2. Copy `VaultUpdateSafeMode.cmd` into the Vault application root beside `Vault.vbs`.
3. Drop `Vault_F21-F40_Portability_Forgejo_SourceControl_RootPatch.zip` into that same application root.
4. Start `VaultUpdateSafeMode.cmd`.
5. The safe launcher temporarily restricts intake to the Vault application root and runs **patch-apply only** through the old operation host.
6. After the patch succeeds, the launcher clears the root-only intake override and starts Vault normally.
7. Confirm the header reports `0.3.0-F21-F40`, then select Vault and run **FULL GATE / CERTIFY GREEN** normally.
8. Downloads monitoring is restored. Rejected/legacy Downloads transports are review items and no longer fail unrelated project gates.

The safe launcher does not delete or modify malformed Downloads files. It only avoids letting the old 0.2.0 gate couple them to the self-update transaction.
