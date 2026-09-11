# Vault F21-F40 — Portability, Drive Catalog, Forgejo and Source Control

## Gate/intake separation

Active-project root drops are the only intake errors allowed to block that project's Build/Quick/Fast/Full operation. Downloads is a global intake surface: malformed or already-seen transports are retained as review evidence and do not fail an unrelated project gate.

Rejected Downloads transports are fingerprinted by path/size/mtime. An unchanged rejection is not re-emitted every watcher cycle. If the file changes it is inspected again.

## Portable D: authority

Vault settings now own three independent paths:

- `vaultHome` — durable Vault data, default `D:\Vault` when D: exists.
- `projectsRoot` — default home for portable projects, default `D:\Projects` when D: exists.
- `scanRoots` — roots indexed for project discovery, default `D:\` when available.

The GUI can migrate Vault Home with hash verification. The previous home is retained as recovery evidence. It can also migrate the active project into the configured Projects Root through a destination-volume staging copy, per-file SHA-256 verification, atomic promotion, stable registry-ID rebinding and source retention for rollback. Project registry records include `portablePath` relative to the configured Projects Root; when that root moves drives, missing absolute paths can rebind to the same relative project location.

Drive scans are asynchronous and build a SQLite project index including nested/composite relationships and discovered project/tooling providers.

## Forgejo integration basis

This pass targets the Forgejo v16 command surface and keeps Forgejo as Vault's local hosted Git authority while GitHub remains a peer remote.

Implemented Forgejo operations:

- server status/version probe
- `forgejo web` start with Vault-owned work/config paths
- managed stop for the process Vault started
- `forgejo doctor check --default --log-file -`
- `forgejo doctor check --all --log-file -`
- timestamped `forgejo dump --file ...`
- `forgejo admin user list`
- `forgejo forgejo-cli actions generate-runner-token`
- `forgejo forgejo-cli actions generate-secret`
- API repository list/create when `VAULT_FORGEJO_TOKEN` is available

Forgejo is deliberately not configured as an automatic push mirror to GitHub by default. Vault uses ordinary Git remotes and non-force pushes to `forgejo` and GitHub-classified remotes. This avoids Forgejo push-mirror force-push behavior overwriting independent GitHub changes.

## Source Control workspace

The Source Control page now separates:

1. Repository Authority status
2. Working Tree
3. Certified GREEN
4. GitHub
5. Local Forgejo
6. Branches / History

Vault-owned Git operations include status, diff/review, init, fetch/prune all, fast-forward-only pull, branch/history/remotes, GitHub push, Forgejo push, both-remote synchronization, and remote add/update.

No Vault path embeds Git credentials. Git authentication remains with the operator's normal Git credential/SSH configuration; Forgejo API token input is via `VAULT_FORGEJO_TOKEN` for this milestone.

## Workspace command presentation

Dynamic middle-column operation pages now use categorized vertical command rows rather than flat button grids. Each row identifies the command and a concise description of what it does, matching the left operation rail's visual rhythm while keeping the persistent console on the right.
