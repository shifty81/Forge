# ForgePY F456-F485 — Unified Vault / Project / Workspace Workflow

This update is cumulative with F450-F455. It is a **plain root overlay**: extract the ZIP
directly over the ForgePY repository root and overwrite matching files.

## Locked user workflow

### Application shell

- **Vault** is the startup/home surface.
- **Project** is the selected-project Dashboard / operations surface.
- **Workspace** is the focused IDE/authoring surface.
- **Settings** remains global.
- The Project Console remains visible beside workspaces and is the future Cortex execution surface.
- Top-level Projects, Source Control and Cortex navigation are collapsed into the above workflow.
- The existing shell geometry, health rail, console pane and status bar are retained.

### Contextual quick bar

The top quick bar now follows the active workspace rather than exposing the same hard-coded
buttons everywhere.

- Vault: Scan Library / Register-Audit / Select Patch / Refresh.
- Project: Full Gate / Build / Run / Apply Updates / Refresh.
- Project Updates: Select Patch / Apply Updates / Refresh.
- Workspace: Build / Run / Full Gate / Refresh.
- Project Console stays globally reachable.

### Patch/update lifecycle

Selecting or dropping a patch is **queue-only**:

1. Inspect transport.
2. Resolve its intended registered project.
3. Verify compatibility.
4. Ask for queue approval.
5. Queue it to that project.
6. Stop.

No project files are modified by Select Patch.

Applying is explicit from the selected project's Dashboard/Updates surface:

1. Apply Updates.
2. Revalidate queue.
3. Transactionally apply.
4. Run authoritative Full Gate.
5. Record GREEN / lineage evidence.

Ordinary Full Gate, Build, Quick and Fast operations do not implicitly consume queued patches.

### Project onboarding

Every registered/scanned project automatically receives a refreshed audit, ForgePY Support Handoff, Project Integration Handoff, and Project Intelligence snapshot in its Vault/Artifact Central report area.

Each project can be audited against ForgePY Project Protocol v1. The audit writes:

- `PROJECT_AUDIT.json`
- `FORGEPY_SUPPORT_HANDOFF.md`
- `PROJECT_INTEGRATION_HANDOFF.md`
- `PROJECT_INTELLIGENCE.json`

The support handoff belongs in the ForgePY development conversation. The integration handoff
belongs in the project's own development conversation.

### CLI / Cortex foundation

`ForgeUnifiedCli.py` and `ForgeUnifiedServices.py` expose the same project/audit/patch/operation
services intended for GUI, headless automation and future Cortex chat integration.

The operation stream uses structured envelopes so Cortex does not need to scrape terminal text.

## Candidate-safe overlay strategy

This package deliberately does not replace these high-churn local candidate files:

- `app/ForgeGui.py`
- `app/ForgeSimplifiedUX.py`
- `app/VaultIntake.py`

`ForgeRuntimeCompatibility.py` patches the existing SimplifiedUX extension point during import,
so local candidate GUI work is preserved while the new workflow is installed.

## Pass map

- F450-F455: prior stabilization/performance repair carried forward.
- F456-F459: canonical Project Protocol / capability vocabulary.
- F460-F463: backend capability truthfulness and compliance normalization.
- F464-F467: CommandBus v3 and structured operation envelopes.
- F468-F474: Project Audit, certification grading, two handoffs, project intelligence snapshot.
- F475-F480: unified Vault/Project/Operation service layer and queue-only patch API.
- F481: explicit-only patch adoption policy in operation host.
- F482-F485: Vault-first GUI normalization, contextual quick bar, duplicate top-level navigation collapse, Cortex/console-ready workflow.
