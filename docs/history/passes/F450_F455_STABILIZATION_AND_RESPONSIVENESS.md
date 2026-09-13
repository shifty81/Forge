# ForgePY F450-F455 cumulative stabilization

This archive is a plain root overlay. Extract it directly over the ForgePY repository
root and overwrite matching files. There is no installer, repair script, bootstrapper,
or second deployment step.

Included passes:

- F450: restore `ForgeSourceAuthority.safe_branch_name`.
- F451: tolerate browser duplicate suffixes such as ` (1).patch`.
- F452: declared-project patch routing uses a registry fast path.
- F453: genuinely unassigned unified diffs use bounded parallel `git apply --check`
  probes for routing only; apply-time validation remains authoritative.
- F454: disabled `driveWatcher` makes startup drive census zero-work.
- F455: candidate-safe compatibility hook supplies missing `re` and corrects the known
  64-bit Windows WNDPROC signature without overwriting `ForgeSimplifiedUX.py`.

High-churn candidate files deliberately NOT replaced:

- `app/ForgeSimplifiedUX.py`
- `app/ForgeF440Normalization.py`
- `app/VaultIntake.py`
- `app/ForgeGui.py`

Deployment:

1. Close ForgePY.
2. Extract ZIP directly into the ForgePY root.
3. Overwrite matching files.
4. Launch ForgePY.
5. Run Full Gate.
