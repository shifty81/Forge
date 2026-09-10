# Vault F60R1 — Downloads Catalog-Only Hotfix

## Rule

`Downloads` and other global watched folders are **intake/catalog surfaces, never execution surfaces**.

A package discovered in Downloads can be:

- `AVAILABLE` — structurally valid and associated with a project, retained under that project's Artifact Central `patches/available/` area;
- `REVIEW` — legacy, malformed, oversized, unbound, or otherwise non-executable evidence retained under Artifact Central `review/`;
- ordinary recognized artifact — archived to the appropriate Artifact Central category;
- unknown content — left alone.

Neither `AVAILABLE` nor `REVIEW` can be staged by `stage_for_project()`.

## Executable update authority

Only a deliberate patch transport dropped into the **active project root** is auto-promoted to `QUEUED`.  Before a build, gate, or explicit Apply Updates, Vault stages only `QUEUED` items matching that active project's identity and verifies the target build/source preconditions again.

Project operations no longer poll Downloads at all.  The background/manual intake service owns Downloads scanning independently.

## Safety result

Running FULL GATE, BUILD, QUICK, FAST, or APPLY UPDATES cannot cause a random matching package sitting in Downloads to become executable.
