# Patch Lineage and `incoming.patch`

F60R9 establishes a hard separation between discovery and execution.

## Rules

1. Downloads and watched global folders **never queue or apply patches**.
2. Historical, legacy, mismatched, invalid, superseded, and otherwise non-current packages are retained under that project's Artifact Central Patch Lineage when the project can be identified.
3. A current modern package discovered in Downloads is only a non-executable `CANDIDATE`.
4. A candidate enters the executable queue only after explicit user approval and a second live hash/build/source verification.
5. The only project-root filename that expresses update intent is `incoming.patch`.
6. `incoming.patch` must be a modern build-bound Forge/Vault patch whose project, date evidence, and live preconditions match the selected project before it becomes `QUEUED`.
7. Arbitrary `*Patch*.zip` files in a project root are lineage evidence, not executable updates.
8. Queue rows from pre-F60R9 releases that lack durable approval evidence are automatically demoted to Patch Lineage before health counts or staging.
9. Canonical Forge patches are applied directly from Artifact Central. `updates/inbox` is used only as an explicit compatibility bridge for legacy project-native PCC patch authorities.
10. Forge's generic health/update counter does not infer pending updates from raw ZIP files or historical `updates/inbox` contents.

## State machine

```text
Downloads / watched folder
        |
        +-- invalid but attributable ------> LINEAGE/invalid
        +-- legacy/unbound ----------------> LINEAGE/legacy
        +-- base mismatch -----------------> LINEAGE/base-mismatch
        +-- modern current-base -----------> CANDIDATE
                                               |
                                      explicit approval
                                               |
                                               v
                                            QUEUED
                                               |
                                          live recheck
                                               |
                                               v
                                            STAGED
                                               |
                                         transactional apply
                                               |
                                               v
                                            APPLIED

project root/incoming.patch
        |
   validate identity/date/base/hash
        |
        +-- mismatch ----------------------> LINEAGE + operation failure
        |
        +-- match -------------------------> QUEUED
```

`CANDIDATE` and `LINEAGE` never contribute to `Updates: N pending`.
