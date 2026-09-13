# ForgePY F60R375 — Earliest-bootstrap diagnostics

F60R374 removed the Tk splash, but the preferred launcher could still disappear without a useful log if the process failed during module import or before Vault-backed crash diagnostics were established.

F60R375 changes the diagnostic boundary rather than adding another startup window:

- `ForgePYBootstrap.py` uses only the standard library plus a tiny package-local logger before importing the application.
- Every launch writes `ForgePY\\logs\\bootstrap\\forgepy-bootstrap-latest.log` when the package directory is writable, with LocalAppData and TEMP fallbacks.
- `ForgeStandalone` no longer imports `ForgeGui` at module-import time.
- Bootstrap phases are flushed before and after the ForgeStandalone import, target resolution, layout initialization, ForgeGui import, GUI construction, and mainloop.
- ForgeGui itself writes phase markers around Tk import/root creation, project contract/backend setup, runtime services, shell construction, project refresh, and mainloop.
- `ForgePYDebug.cmd` always keeps a diagnostic console open after ForgePY exits.

There is still no startup splash or second Tk root in the normal path.
