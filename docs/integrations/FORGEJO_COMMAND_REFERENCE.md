# Forgejo Command Reference Used by Vault

Target documentation family: Forgejo v16.x.

Vault uses only documented server/admin command shapes in this milestone:

```text
forgejo --work-path <path> [--config <app.ini>] web --port 3000
forgejo --work-path <path> [--config <app.ini>] doctor check --default --log-file -
forgejo --work-path <path> [--config <app.ini>] doctor check --all --log-file -
forgejo --work-path <path> [--config <app.ini>] dump --file <timestamped.zip>
forgejo --work-path <path> [--config <app.ini>] admin user list
forgejo --work-path <path> [--config <app.ini>] forgejo-cli actions generate-runner-token [--scope owner/repo]
forgejo --work-path <path> [--config <app.ini>] forgejo-cli actions generate-secret
```

Repository creation/listing uses Forgejo's HTTP API and is enabled only when `VAULT_FORGEJO_TOKEN` is available.

Vault's cross-host synchronization uses normal Git remotes rather than Forgejo push mirrors. A Forgejo push mirror can use `git push --mirror` and force-push its target; Vault therefore keeps independent Forgejo/GitHub remotes and pushes the current branch without `--force`.
