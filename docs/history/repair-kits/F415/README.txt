ForgePY F415 one-time overwrite repair

Fixes:
- Patch Review no longer destroys its own Treeview when Route opens a text prompt.
- Restores the missing project-target resolver used by Approve / Approve + Apply.
- Renames Queue -> Approve and Queue + Apply -> Approve + Apply + Gate.
- Current-project approved updates use ForgePY's direct transactional universal patch lane
  instead of bouncing through the legacy ProcessHost patch-apply path.
- Already-approved QUEUED/STAGED updates are surfaced by Check for Updates and can resume.
- Python provider output is forced unbuffered for live Project Console streaming.
- Tkinter callback exceptions are routed into the ForgePY Project Console instead of stderr.
- Normal ForgePY.cmd launch uses the no-console ForgePY.vbs/pythonw lane.
- ForgePY-Debug.cmd remains available for deliberate foreground/bootstrap diagnostics.

Install:
1. Let any genuinely active patch transaction finish if it is still making progress.
2. Fully close ForgePY.
3. Extract this ZIP directly into the ForgePY root and allow overwrite.
4. Relaunch with ForgePY.cmd (normal no-console launch).
5. Select the project and use Check for Updates.
   - If the patch is already QUEUED, ForgePY will offer Resume Apply + Full Gate.
   - If it is in REVIEW, open Patch Review and use Approve or Approve + Apply + Gate.
6. Use ForgePY-Debug.cmd only when you intentionally want an external diagnostic console.

This repair does not advance the ForgePY version.
