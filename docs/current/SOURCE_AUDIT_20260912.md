# ForgePY Source Audit and Normalization — 2026-09-12

## Authority state

The uploaded repository is based on committed/certified build `FORGEPY-F60R415` at Git commit `4cea5cf`, with the later F416–F740 candidate work integrated in the working tree. This normalization advances the visible candidate identity to `0.5.0-candidate.741` / `FORGEPY-F741`; it does **not** relabel the committed F60R415 baseline as newly Windows-certified.

## Audit findings

### Repository/source authority

The uploaded ZIP contained two overlapping source trees: the canonical repository root and a nested `ForgePY/` mirror. Current package/source policy already identified the nested tree as a legacy mirror, so keeping it in the source snapshot created ambiguity without providing runtime authority. The cleaned snapshot contains one canonical source tree only.

The root also contained one-time F415/F416–F441/F444 overwrite repair payloads, repair scripts, live `logs/`, `artifacts/`, `hotfix-backups/`, Python bytecode, and obsolete repository-replacement publishing helpers. These are not current product source. Historical repair readmes/manifests have been retained under `docs/history/repair-kits/`; executable overwrite payloads and runtime/transient data are excluded from the normalized source snapshot.

### Documentation

The previous `docs/` root mixed current architecture, operator guides, integration notes, pass plans, hotfix history, and candidate certification evidence. Documentation is now divided into `current/`, `architecture/`, `guides/`, `integrations/`, and `history/`, with `docs/README.md` as the index.

### GUI/runtime regression found from live Windows evidence

The candidate UI removed the old Dashboard summary widget but `_render_status()` still assumed `self.summary_text` existed. A live Cortex Full Gate produced `AttributeError: 'ForgeGui' object has no attribute 'summary_text'`. Status rendering now tolerates the simplified layout and no longer requires the retired widget.

The global console also exposed duplicate Stop controls and retained Last Run state in the workspace header. The normalized contract is:

- one `Stop` control only;
- `Stop` is adjacent to `Run`/Send in the global console command row;
- Stop requests cancellation of the current foreground console/PCC operation and terminates the tracked child process tree without blocking Tk;
- `stop`, `cancel`, `interrupt`, and `stop job` resolve to cancellation behavior;
- operator cancellation renders as `STOPPED`, not a normal failure;
- `Last Run` is a persistent bottom-status-bar field rather than a console/workspace header field;
- the version remains at the far-right edge of the bottom status bar.

The universal Apply + Full Gate lane and ForgePY self-update loop now observe the same cancellation state between safe transaction boundaries. An in-progress atomic patch write is not interrupted mid-transaction; cancellation takes effect at the next safe boundary or against a tracked child gate process.

### Test/contract normalization

The first integrated test run exposed stale test assumptions as well as real API/runtime gaps. The stale cases included fixed September 10 patch timestamps that had correctly aged into the newer historical-lineage rules, overlay-era assertions that canonical GUI files must not exist, and older expectations that build/full implicitly apply queued patches. These tests were migrated to the current fail-closed patch architecture rather than weakening the safety rules.

`ForgeSourceAuthority` now has a real audit API used by the Full Gate, and `ForgeJobs` retains completed futures long enough to avoid the completion/removal race seen by callers.

After these corrections, the existing integrated suite passed **385/385 tests** before repository-structure enforcement tests were added.

## Root contract after normalization

The normal root surface is limited to:

- product launchers: `ForgePY.vbs`, `ForgePY.cmd`, `ForgePYConsole.cmd`, `ForgePY-Debug.cmd`;
- compatibility aliases: `Forge.vbs`, `Forge.cmd`, `ForgeConsole.cmd`;
- verification: `VerifyForgePY.cmd` plus the legacy `VerifyForge.cmd` alias;
- product/contract files: `README.md`, `CHANGELOG.md`, `requirements.txt`, `project.control.json`, `FORGEPY_PACKAGE_MANIFEST.json`, `.gitignore`;
- source/content directories: `app/`, `assets/`, `compat/`, `docs/`, `reference/`, `tests/`, `tools/`, `web/`, `archive/`.

No nested source mirror, runtime logs, build output, repair payload, or patch transport belongs in that root contract.

For an existing checkout that receives the incremental F741 patch, the legacy nested `ForgePY/` mirror is intentionally outside normal patch governance. Audit it with `python tools/repository/NormalizeForgePYSource.py --root .`; use `--apply` only when you explicitly want to remove the known legacy mirror/repair residue and Python caches. The clean replacement source package is already normalized.

## Certification boundary

The Python test/gate work in this normalization can validate source coherence in the current environment, but Windows-native GUI behavior, packaged EXE/installer output, system-tray behavior, and real process-tree cancellation still require the normal ForgePY Full Gate/runtime certification on the Windows development machine. F741 should remain a candidate until that native certification is completed.
