ForgePY F444 DIRECT OVERWRITE SOURCE

Purpose
-------
This corrects the launcher regression and the three stale Full Gate assertions shown
in the latest ForgePY Full Gate output.

Normal launch contract
----------------------
ForgePY.vbs                 = preferred truly no-console GUI launcher
ForgePY.cmd                 = compatibility shim that immediately delegates to VBS/pythonw
ForgePY-Debug.cmd           = explicit foreground diagnostic console launcher
ForgePYConsole.cmd          = emergency CLI/console mode

Important Windows note
----------------------
Double-clicking ANY .cmd file can cause Windows itself to flash a console briefly before
the batch file delegates. If you want zero console flash, launch ForgePY.vbs (or a shortcut
whose target is ForgePY.vbs). The future packaged executable will replace this distinction.

Also fixed
----------
- Updates the old F60R66 and F60R372 tests so Full Gate no longer forces the obsolete
  foreground-console launcher back into ForgePY.
- Updates the F60R415 cross-project patch test so it certifies the real invariant
  (resolved target is used without switching the visible project) rather than one old
  variable-name/source-string shape.
- Retains F416-F443 normalization, live Project Console streaming, patch/update fixes,
  fallback debug handoff, and provider/operations work.

Install
-------
1. Fully close ForgePY.
2. Extract directly into C:\Users\Shifty\Desktop\ForgePY
3. Allow overwrite.
4. Launch ForgePY.vbs for the console-free GUI path.
5. Run Full Gate.
