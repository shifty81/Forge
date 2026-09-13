# ForgePY F754 — Already-target patch routing

F754 fixes manual patch intake when the selected transport has already been fully applied.

## Behavior

- The resolver distinguishes `ALREADY_TARGET` from `INCOMPATIBLE`.
- Target satisfaction requires the declared target build/version and the patch target file hashes to match the live project.
- Selecting the same cumulative patch twice does not queue or reapply it.
- The GUI reports **Patch Already Applied** as informational state instead of **Patch Target Requires Review**.
- The redundant transport is retained as inert `already-applied` Patch Lineage and never contributes to pending updates.
- Normal precondition enforcement is unchanged for patches that are not already fully materialized.

This closes the F753 routing defect where an F742→F753 cumulative patch selected on an already-F753 checkout was misclassified as incompatible.
