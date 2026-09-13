ForgePY F416-F441 Cumulative Overwrite Repair

Purpose
-------
Use this package when ForgePY cannot apply the cumulative .patch cleanly because the
working tree already contains partial F416-F440/F441 changes or repair hotfixes.

This package DOES NOT use ForgePY patch intake to modify the source. It backs up the
four affected files and overwrites them with the complete cumulative F415-repair +
F416-F440 normalization + F441 live-console/Project-CLI source.

Included overwrite files
------------------------
app\ForgeSimplifiedUX.py
app\ForgeF440Normalization.py
app\ForgeProviderProtocol.py
tests\test_forgepy_f416_f440_normalization.py

Install
-------
1. Fully close ForgePY.
2. Extract this ZIP directly into your ForgePY root.
3. Run RUN_REPAIR.cmd.
4. The script backs up existing affected files under:
     artifacts\repair-backups\F416-F441-<timestamp>
5. It clears stale __pycache__, compiles the changed Python files, and runs the
   F416-F441 normalization regression tests.
6. Relaunch ForgePY and run FULL GATE.

The reference cumulative diff is included as:
reference\ForgePY__20260912__F416-F441-CUMULATIVE_FROM_F415-REPAIRED.patch.txt

It is deliberately .patch.txt so ForgePY's intake watcher will not ingest the
reference patch while this overwrite repair is being installed.

Important
---------
This repair intentionally leaves the visible ForgePY version at the current F415
identity until the Windows Full Gate certifies the normalization tranche GREEN.
