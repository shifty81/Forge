# ForgePY F60R390 — Embedded Dialog Completion

ForgePY-owned secondary Tk windows have been removed from `ForgeGui.py`. Vault lineage, Artifact Central, Patch Review/Routing, and downloaded-update selection now render as embedded action surfaces inside the main ForgePY shell. Native Windows file/folder pickers remain OS dialogs but are explicitly parented to the ForgePY main window so they remain owned by ForgePY. Startup-fatal dialogs in the pre-GUI bootstrap are intentionally retained because no application shell exists at that point.
