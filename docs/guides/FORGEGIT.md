# ForgeGit

ForgeGit is ForgePY's first-class local source-control and recovery authority. It uses standard bare Git repositories, not a proprietary format. GitHub remains the standard external remote. Forgejo is optional compatibility hosting.

## Authority

Each registered project may bind the canonical `forgegit` remote to `<ForgePY Home>/ForgeGit/<project-id>.git`. ForgePY discovers and adopts legacy `InternalGit` repositories and the old `forgepy-internal` remote so existing history is not lost during normalization.

## Normal workflow

1. Run the project-owned Full Gate / Certify GREEN.
2. Use ForgePY **Commit GREEN** or **Commit + Push GREEN**.
3. The working Git repository receives one commit.
4. ForgeGit snapshots that exact commit locally.
5. GitHub receives the same commit when configured.
6. ForgePY writes source-control receipts into Artifact Central.

## Recovery

ForgeGit supports named recovery branches, branch history, integrity verification, portable verified Git bundles, and recovering a ForgeGit branch into a new local branch without rewriting the active working tree.
