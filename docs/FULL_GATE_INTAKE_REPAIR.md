# Full Gate Intake Repair

## Symptom

A Full Gate could fail because unrelated malformed/duplicate patch ZIPs were sitting in the global Downloads directory. The same unchanged files were then re-reported by the background watcher, producing repeated warnings.

## Repair

F21-F40 splits intake authority:

- active project root: blocking, because a patch deliberately dropped there is part of the requested project operation;
- Downloads: global/background, non-blocking for the active project gate;
- unchanged rejected Downloads transports: cached and suppressed until their size or modification time changes.

This allows an unrelated project's Full Gate to continue while Vault retains Downloads rejections for later review.
