# ForgePY F445-F449 high-value gap closure

These five passes sit on top of the Windows-GREEN F444 normalization candidate.

- **F445 — Patch observability:** Updates gains an explicit Details surface and canonical patch metadata/status rendering.
- **F446 — Patch preflight:** READY/QUEUED patches validate immutable transport + resolved target before apply; queued resume uses the catalog-bound target root rather than the currently visible workspace.
- **F447 — Patch lineage policy:** `conflictsWith` joins `requires` and `supersedes` in the normalized update policy.
- **F448 — Provider hygiene:** persistent Operations only exposes VERIFIED/CERTIFIED project tools; provider compatibility gets one structured report.
- **F449 — Canonical source authority:** Full Gate verifies root/app is the runtime authority and warns (without failing) when the nested package/reference mirror has drifted.

The core visible release identity intentionally remains F415 during this candidate run. The GUI displays `F449 candidate` honestly. After this patch applies and the Windows Full Gate is GREEN, promote the release/version authority to F449 as the next build/release step.
