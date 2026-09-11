# ForgePY F60R374 — Direct-launch rollback

The temporary startup launcher/self-test surface introduced during the Windows startup stabilization sequence has been removed from the normal application path.

Normal ForgePY launch is now intentionally simple:

1. resolve a valid project shell (or ForgePY itself);
2. create/verify machine-local ForgePY directories without Tk;
3. initialize first-run state if needed;
4. construct `ForgeGui` directly;
5. enter the main GUI event loop.

There is no splash Tk root, no root handoff, no splash worker, and no pre-GUI repair gate during normal launch. Deep package verification remains available through `VerifyForgePY.cmd`.

This is a deliberate rollback of the startup-launcher concept because the Windows host repeatedly showed launch/close regressions after it was introduced.
