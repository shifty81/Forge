# ForgePY F60R378 — Global Patch Target Authority

Patch target selection is independent of the active ForgePY workspace.

## Resolution rules

1. Manifest-backed Forge patches use their declared project identity and are checked only against matching registered projects.
2. Git unified-diff `.patch` transports with no declared project are checked with the governed patch validator against every registered project.
3. Exactly one compatible project is automatically resolved.
4. Zero matches remain non-executable/reviewable.
5. More than one match is AMBIGUOUS and ForgePY refuses to guess.
6. Approval records the resolved target root and project before anything can enter the executable queue.

The selected Workspace/Project tab is presentation context only. It is not patch routing authority.
