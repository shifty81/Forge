# F767-F776 — Native GUI Wave 2: Docking Polish + Project Intelligence

Forge Native remains **SHADOW**. Python ForgePY remains the certified backend/recovery authority while the Rust application becomes the primary development target.

## Passes

1. **F767 — Shell parity refinement**: project-aware identity fallback, governed Run routing, and quickbar queue/intelligence access.
2. **F768 — Semantic widget registry**: Project, Operations, Workspace and System widget categories with reopenable dock tabs.
3. **F769 — Layout presets**: Forge, Operations and Intelligence layouts built on the same `egui_dock` authority.
4. **F770 — Layout lock + persistence**: saved lock/compact-health state; lock disables tab dragging/closing without destroying the current layout.
5. **F771 — Foreground queue workspace**: visible active/pending/last-run state, pending-job cancellation and queue clearing.
6. **F772 — Native zero-tooling census**: bounded project scan with generated/cache pruning, build-system markers, language counts and nested-root hints.
7. **F773 — Toolchain Intelligence**: bounded PATH discovery for Git, Rust, Python, CMake/Ninja, MSBuild/.NET, Node/npm, JVM/Gradle/Maven and Godot.
8. **F774 — Safe operation synthesis**: evidence-only build/test/check candidates inferred from project structure without requiring Forge scripts or a PCC.
9. **F775 — Project Intelligence widget/headless evidence**: native GUI inspection surface plus `--intelligence-json` / ForgePY audit lane.
10. **F776 — Wave 2 parity/certification**: candidate/native identity advanced, parity matrix updated and regression coverage added without claiming native takeover.

## Safety rules

- Census is bounded to 12,000 entries and depth 4.
- `.git`, `.forge`, IDE metadata, `target`, `node_modules`, build outputs, logs and artifacts are not recursively descended.
- Inferred operations are shown as evidence only in this wave; execution still uses governed project/PCC operations until direct-command policy is certified.
- One active foreground operation is retained. Additional operations queue with project/root binding and duplicate coalescing.
- Rust does not become `PRIMARY` from GUI completion alone; SQLite/Vault, updates/patches, source control, settings and direct operation execution still block takeover.
