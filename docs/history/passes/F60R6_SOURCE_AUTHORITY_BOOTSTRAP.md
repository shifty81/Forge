# Forge F60R6 — Source Authority Bootstrap

F60R6 closes the first-repository bootstrap gap exposed by an installed Forge tree whose `.git` directory existed but had no local `HEAD` and no GitHub remote.

## Source-control rules

- Forge is the universal source-control orchestrator.
- `ForgeSourceControl.py` is authoritative; `VaultSourceControl.py` is a compatibility shim.
- A project may declare its GitHub authority in `project.control.json` under `sourceControl.github`.
- Project registration and the Open GitHub action can use that declaration even before a live Git remote exists.
- Initialize / Adopt Git never replaces working-tree files.
- When the local repository is unborn and the declared GitHub remote already has `main` history, Forge fetches that history and performs a mixed reset to the remote branch. This establishes the remote commit as the local parent while preserving every current working-tree byte as a reviewable replacement diff.
- Review Changes and Full Diff are valid on an unborn repository and never call `git diff HEAD` against an invalid HEAD.
- Push requires an actual local commit and gives a guided failure otherwise.

## Universal GREEN authority

After every successful Forge-hosted Full Gate, Forge records a durable governed-source SHA-256 fingerprint in Artifact Central rather than inside the project repository. This prevents certification metadata from making the working tree dirty and lets generic projects use the same protected Commit GREEN workflow.

Project-native GREEN/commit tooling still outranks the generic fallback when a project already provides stronger behavior.
