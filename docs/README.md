# ForgePY Documentation

This directory is the documentation authority for ForgePY. The repository root intentionally carries only the product entry points, project/package contracts, README/changelog, and source/tool directories.

## Current documentation

- [`current/`](current/) — current source audits, normalization checkpoints, and handoff state.
- [`architecture/`](architecture/) — product architecture, module authority, project contracts, and root/source-tree policy.
- [`guides/`](guides/) — operator and developer workflows: onboarding, discovery, Full Gate, updates, recovery, source control, and portability.
- [`integrations/`](integrations/) — external tooling and compatibility/reference integrations.

## Historical documentation

- [`history/passes/`](history/passes/) — completed pass plans, gap audits, hotfix notes, and superseded implementation notes.
- [`history/certification/`](history/certification/) — historical candidate overlay manifests and certification evidence.
- [`history/repair-kits/`](history/repair-kits/) — retained documentation/manifests from one-time overwrite repairs. Executable repair payloads are intentionally not part of the current source tree.
- [`history/legacy-pcc/`](history/legacy-pcc/) — pre-ForgePY standalone PCC documentation retained for provenance.

## Documentation rules

1. Current architecture or operator guidance belongs in `architecture/`, `guides/`, or `integrations/`.
2. Pass-numbered implementation notes are historical once their code is integrated and belong in `history/passes/`.
3. Candidate certification artifacts are evidence, not active product documentation, and belong in `history/certification/`.
4. One-time repair kits must never return to the repository root. Preserve only documentation required for provenance.
5. Root-level `README.md` and `CHANGELOG.md` are the only general product documents kept at repository root.
