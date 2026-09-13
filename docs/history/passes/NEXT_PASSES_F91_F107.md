# ForgePY F91-F107 Normalization Tranche

- F91 Workspace geometry normalized: compact operation rail, wider control surface, console default reduced to ~38%.
- F92 Project Health / Patch Intake / Project Context rail is permanent application chrome.
- F93 Header density reduced without changing ForgePY's visual language.
- F94 Workspace splitter positions persist through ForgePY settings.
- F95 Central thread-safe EventBroker added.
- F96 Shared ForgeWorkerPool added for background jobs.
- F97 Existing bounded/batched console contract retained and normalized as performance authority.
- F98 Heavy app workspaces are lazy-built when opened rather than all at startup.
- F99 Performance telemetry extended with UI event-loop lag probe.
- F100 Every normal GUI launch runs a visible startup self-test/progress screen.
- F101 First-run detection initializes machine-local ForgePY state and records completion.
- F102 New Windows installs prefer D:\\Vault and initialize Vault/Library/Artifact Central/ForgeGit/state/components/adapters.
- F103 Non-destructive background drive census added; it is bounded and never blocks first launch.
- F104 Conservative Repair Mode diagnostics/structure repair added; application source remains package-authoritative.
- F105 Universal Tool Registry defines project/global/family tool identity, capabilities, readiness and execution metadata.
- F106 Tool Scanner activates discovered scripts/declared commands into runnable capabilities and Tooling UI can run selected READY tools.
- F107 Machine-local generated adapters plus Toolchain Doctor provide project-specific capability mapping and missing-runtime/install plans.

The dark/cyan/rounded ForgePY visual language is intentionally unchanged. These passes alter geometry, responsiveness, initialization and capability plumbing rather than redesigning the application.
