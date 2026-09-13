# ForgePY F60R377 — Patch Transport Normalization

ForgePY previously conflated the `.patch` extension with its ZIP-backed `forge.patch.v1` package format.
That was incorrect for project workflows that produce standard Git unified-diff `.patch` files.

F60R377 treats `.patch` as a semantic transport extension with two supported encodings:

1. **Forge package patch** — ZIP container with top-level `PATCH_MANIFEST.json` and payload files.
2. **Git unified diff** — normal text beginning with `diff --git`, validated against the active Git working tree.

Unified diffs are not auto-executed. Manual selection or explicit Downloads approval remains required. Before
queue/apply ForgePY runs `git apply --check`. Application uses normal `git apply` without reject mode, records
recovery preimages, verifies that the patch can be reverse-checked, and emits a normal durable patch receipt.

Modal confirmation windows also remain topmost for their entire modal lifetime so clicking the main ForgePY
window cannot bury the active confirmation panel.
