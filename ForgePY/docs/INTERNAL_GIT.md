# ForgePY Internal Git

ForgePY Internal Git is the local source-control authority used alongside GitHub. It stores normal bare Git repositories under the configured ForgePY data root and uses ordinary Git remotes and objects; there is no proprietary repository format.

Each registered project can bind a deterministic `forgepy-internal` remote to `<ForgePY Home>/InternalGit/<project-id>.git`. **Ensure Internal Git** creates/binds the local bare repository without replacing the project's working tree. **Push Internal Snapshot** pushes the current committed branch into that local authority. GitHub remains the standard external remote. Forgejo is optional compatibility/source-hosting infrastructure and is not required for Internal Git.

Internal Git never commits uncommitted files on the user's behalf. The project's certified GREEN commit path remains authoritative for creating commits; Internal Git stores/preserves those commits locally.
