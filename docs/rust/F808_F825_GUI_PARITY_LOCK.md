# Forge Native F808-F825 — GUI Parity Audit + Shell Lock

Baseline: certified ForgePY / Forge repository F797 (`d0c0f4afbba7046bc35026a2858696cd5f92b593`) plus the cumulative F798-F807 native self-update foundation overlay.

## Decision

The Rust lane now has one locked GUI composition. Future parity work must migrate capability into these regions instead of inventing new top-level shells or duplicate consoles.

```
FORGE NATIVE
┌──────────┬───────────────┬────────────────────────────┬─────────────────────────┬──────────────────────┐
│ FORGE    │ PROJECT       │ QUICKBAR / WORKBENCH       │ FORGE CONSOLE           │ PROJECT CONTEXT      │
│ RAIL     │ RAIL          │                            │ permanent               │ / INTAKE             │
│          │               │ central ForgeDock only     │ channel/status strip    │ intake / next gate   │
│ Vault    │ Overview      │                            │ ALL PROJECT FORGE       │ compact health       │
│ Project  │ Source        │                            │ BUILD GATE PATCH        │ active job           │
│ Workspace│ Build & Test  │                            │ GIT DOCTOR              │ recent               │
│ Settings │ Run           │                            │ command composer        │ alerts/dependencies  │
│          │ Updates       │                            │                         │                      │
│          │ Intelligence  │                            │                         │                      │
│          │ Native        │                            │                         │                      │
│          │ Diagnostics   │                            │                         │                      │
│          │ Artifacts     │                            │                         │                      │
│          │ Project Tools │                            │                         │                      │
├──────────┴───────────────┴────────────────────────────┴─────────────────────────┴──────────────────────┤
│ STATUSBAR                                                                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Protected shell contract

Seven regions are permanent:

1. Forge rail
2. Project rail
3. Quickbar
4. Workbench
5. Forge Console
6. Project Context / Intake rail
7. Statusbar

Only **Workbench** is dockable. Forge Console is no longer a normal ForgeDock tab. A persisted v2 layout cannot re-introduce the old dockable-console topology because the storage key moves to v3.

## Visual lock

- Native product label is `Forge`, not `ForgePY.Native`.
- Dark theme remains authoritative.
- Visible controls/panels use normalized rounded-corner tokens.
- Compact health replaces the oversized semicircle gauge.
- The right rail is collapsible but remains the only user-facing intake home.
- Project CLI remains explicit and distinct from Forge Console.
- Console is permanent and gets an operator channel strip: ALL / PROJECT / FORGE / BUILD / GATE / PATCH / GIT / DOCTOR.
- Workbench layouts/presets may move tabs, but cannot move shell chrome.

## Front-to-back parity audit

States:
- **PASS** — native Rust GUI owns the interaction/surface now.
- **PARTIAL** — native landing surface exists, but Python ForgePY remains backend authority.
- **MISSING** — meaningful ForgePY functionality has not yet moved into Rust.
- **SUPERSEDE** — Rust target intentionally replaces the older Python presentation model.

| Capability | ForgePY authority | Rust F825 | Required migration |
|---|---|---:|---|
| Primary app rail: Vault / Project / Workspace / Settings | canonical | PASS | keep locked |
| Contextual Project rail | canonical | PASS | capability visibility from provider metadata next |
| Quick actions | canonical | PASS | add per-surface action sets after command registry migration |
| Permanent Forge Console | canonical | PASS | console bus/channel metadata next |
| Console source/status header | requested normalization | PASS | replace heuristic filters with typed channels |
| Project Context / Intake rail structure | canonical target | PASS | backend fields still partial |
| Governed patch/file intake | Python | PARTIAL | native intake service + classification + lineage |
| Downloads watcher classification | Python | MISSING | migrate after native catalog |
| Next Full Gate projection | Python | PARTIAL | typed queued-patch/gate plan |
| Compact project health | Python | PASS UI / PARTIAL DATA | native health service parity |
| Active job / recent activity | Python | PASS | expand durable history |
| Bottom statusbar | Python | PASS | Git/branch/dirty parity next |
| Rounded theme/components | mixed Tk/ttk | SUPERSEDE/PASS | visual Windows soak |
| Centered owned modals / topmost dialogs | Python policy | MISSING | native modal service |
| Dock/workbench persistence | Rust | PASS | add layout migration versioning |
| Project discovery/registration | Python/Vault | PARTIAL | native registry/catalog authority |
| Project dashboard | Python | PARTIAL | full health/update/source summaries |
| Project operation queue | bridge | PASS UI / PARTIAL EXEC | direct Rust governed execution |
| Build/Test/Run/Full Gate | project PCC/Python bridge | PARTIAL | provider contract executor in Rust |
| Internal PCC discovery/launch | Python bridge | PARTIAL | first-class provider contract runtime |
| Project CLI | Python/project PCC | PARTIAL | typed command catalog/completion |
| Source Control / ForgeGit | Python | MISSING/PARTIAL LANDING | internal bare repos, branch/history/recovery UI |
| GitHub remote | Python | MISSING | remote status/push/pull/auth UI |
| Forgejo compatibility | optional Python | DEFER | compatibility/import only; no separate product |
| Vault Explorer | Python | MISSING | Explorer-like tree/list/details/thumbs/search |
| Vault catalog SQLite/WAL | Python | MISSING | native durable catalog is takeover blocker |
| Artifact Central | Python | PARTIAL LANDING | native artifact browser/receipts/lineage |
| Backup asset catalog / hash hydration | Python | PARTIAL BRIDGE | native resolver + provenance UI |
| Project Intelligence | Rust bounded census | PARTIAL | durable profiles + incremental index |
| Toolchain intelligence | Rust PATH probe | PARTIAL | versions/capability confidence/cache |
| Tool Registry / verified project tools | Python | PARTIAL | native provider-fed tool catalog |
| Diagnostics / Doctor | Python bridge | PARTIAL | native health rules and debug bundle orchestration |
| Recovery / rollback | Python/Internal Git | PARTIAL BACKEND | explicit Recovery workbench surface |
| Settings | Python | PARTIAL | schema ownership + integration endpoints |
| Workspace file browser/editor | Python/Tk prototype | MISSING | native Explorer/file tree + text editing |
| Cortex integration | external/bridge | MISSING | global contextual service after Forge core parity |
| Notifications/toasts | Python | MISSING | in-app native notification center |
| Installer/portable packaging | Python | PARTIAL | native packaging parity later |
| Self-update portable/installed | F798-F807 foundation | PARTIAL | Rust archive/hash authority + restart certification |
| System tray | Python disabled on 3.14 path | MISSING | native Windows tray after shell parity |
| Security/credential storage | Python/environment | MISSING | OS credential provider |
| Performance telemetry | Python | MISSING | native timing/event metrics |

## Parity order from here

### Wave A — GUI/data parity (F826-F850)
1. Native intake model + right-rail real data.
2. Typed console channels instead of text heuristics.
3. Native health snapshot and statusbar Git/branch state.
4. Centered owned modal + toast service.
5. Recovery becomes a first-class Project section.

### Wave B — Vault/source parity (F851-F900)
1. SQLite/WAL native catalog.
2. Explorer-like Vault browser.
3. Internal Git / ForgeGit source model.
4. GitHub remote subtab.
5. Artifact Central browser and asset-hydration provenance.

### Wave C — execution parity (F901-F950)
1. Internal PCC Provider contract executes directly from Rust.
2. Canonical project command registry and aliases.
3. Direct Build/Test/Run/Full Gate with streamed output/cancel.
4. Transaction/recovery journal and worktree validation.
5. Patch intake and application fully native.

### Wave D — lifecycle takeover (F951+)
1. Native packaged update archive authority.
2. Installer/portable packaging.
3. Tray/notifications.
4. Security/credentials.
5. Performance soak and parity evidence.
6. Explicit SHADOW -> DUAL-READ -> MIRRORED -> CANDIDATE -> PRIMARY decision.

## Non-negotiable migration rules

- Do not create a second patch engine, source engine, project registry, console, or command model just to fill a Rust panel.
- Until a backend row is native-certified, the Rust surface calls the existing ForgePY/project PCC authority through the bridge.
- Once a native backend reaches parity, switch the row deliberately and keep one compatibility adapter only.
- No backend may change shell geometry.
- No future feature may add a new top-level application surface without revising this contract and its tests.
- Forge Console and Project CLI remain separate concepts.
- The right rail projects state; it does not become a second intake/health/task authority.
