# ForgePY F60R379 — Self-update package boundary normalization

The F60R377 → F60R378 transport accidentally captured `logs/bootstrap/forgepy-bootstrap-latest.log` and other bootstrap logs. Those files are live runtime state and change every time ForgePY starts, so a preimage hash for them is inherently unstable. The F60R378 update therefore failed correctly at preimage validation, but the transport itself was wrong.

F60R379 establishes a single immutable package policy. Runtime logs, Artifact Central output, update inboxes, `.forge` state, build output, hotfix backups, crash dumps and machine-local settings are excluded from release/package/patch authority. `BuildForgePYPatch.py` uses the same policy as the package manifest builder.

ForgePY self-update now preflights all queued transports before applying any. A legacy transport that targets runtime state is quarantined to patch lineage and cannot partially update the application or block a newer safe transport.
