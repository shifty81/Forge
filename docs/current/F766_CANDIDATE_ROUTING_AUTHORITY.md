# F766 Candidate Routing Authority

ForgePY keeps two identities during migration: the last promoted/certified donor build and the active candidate source build. Patch routing must use the active candidate identity when one exists.

Before F766, `VaultBuildIdentity.build_identity()` loaded `ForgePYVersion.py` after `project.control.json` and overwrote the candidate identity with `FORGEPY-F60R415`. This made a valid F764 -> F765 patch look incompatible even while the GUI correctly displayed F764.

F766 makes `candidateVersion` / `candidateBuild` the effective routing identity, preserves the older `version` / `build` values as `certifiedProjectVersion` / `certifiedProjectBuild`, and carries the F765 egui 0.36 compile repair forward.
