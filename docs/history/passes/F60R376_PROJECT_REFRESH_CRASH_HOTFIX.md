# ForgePY F60R376 — Project Refresh Telemetry Crash Hotfix

The F60R375 bootstrap trace identified the first deterministic post-shell crash:

`ForgeGui._refresh_projects()` called `forge_perf_record()` with a metadata dictionary as the third positional argument. `ForgePerformance.record()` defined that position as `threshold_ms` and attempted `float(threshold_ms)`, causing `TypeError: float() argument must be a string or a real number, not 'dict'` immediately after `GUI_SHELL_BUILD_PASS`.

F60R376 fixes both sides: the GUI passes an explicit numeric threshold plus metadata, and the performance recorder is backward-hardened so a mapping in the old third position can no longer terminate the application.
