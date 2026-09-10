# Project Control Center — Standalone Portable Package

Version: **PCC-STANDALONE-0.1**  
GUI: **PCC-GUI-0.10.2**

This package runs the Universal Project Control Center from its own folder. It does **not** need to be copied into Cortex, Codename Subspace, Windstead, Havenwild, or another project in order to open and manage that project.

## Start it

Preferred Windows launcher:

- `ProjectControlCenter.vbs` — launches the GUI with no visible bootstrap console.

Fallback / diagnostic launcher:

- `ProjectControlCenter.cmd` — launches through a visible command shell and keeps errors readable.

Verification:

- `VerifyStandalone.cmd` — verifies Python, Tkinter, and the standalone PCC modules.

You can also pass a project folder explicitly:

```text
ProjectControlCenter.cmd --root "C:\Users\Shifty\Desktop\Cortex-Main"
```

Or force the folder picker:

```text
ProjectControlCenter.cmd --choose
```

## First-launch behavior

1. PCC checks the user-level Project Registry.
2. If a valid active project already exists, it opens with that project selected.
3. Otherwise it shows a folder picker.
4. The selected project is scanned and registered automatically.
5. `project.control.json` is optional. Folder-first auto-discovery can bind existing Cargo, CMake/C++, Gradle, Python, Node, root utility, PowerShell action, Git, update, diagnostics, and runtime tooling.

## Standalone data locations

The portable program files remain in this extracted folder. Persistent user/project metadata does not need to live beside the executable files.

Windows defaults:

```text
%LOCALAPPDATA%\ProjectControlCenter\project_registry.json
%LOCALAPPDATA%\ProjectControlCenter\passports\
%LOCALAPPDATA%\ProjectControlCenter\Vault\
```

The selected project's own build outputs, logs, debug bundles, patch receipts, and project-native state remain under that project according to its authority.

## Important safety behavior

- The standalone application does not require adding a PCC JSON file to a project.
- Auto-discovery is read-oriented during onboarding.
- Repo hygiene moves recognized operational transport/artifacts; it does not reset, stash, hide, or overwrite real source changes.
- Mutating operations still use the selected project's discovered/native command authority.
- GREEN commit/push operations remain gated by the project provider when the project exposes one.
- The embedded console is the normal execution surface.

## Package layout

```text
ProjectControlCenter-Standalone/
├─ ProjectControlCenter.vbs        preferred GUI launcher
├─ ProjectControlCenter.cmd        diagnostic launcher
├─ VerifyStandalone.cmd
├─ requirements.txt
├─ app/                            portable universal PCC runtime
├─ docs/                           architecture/onboarding/recovery notes
└─ reference/
   └─ cortex-project-provider/     Cortex project-side PCC recovery/reference snapshot
```

## Launching Cortex

If Cortex is already registered, just launch `ProjectControlCenter.vbs` and select Cortex from **Projects**. Otherwise choose the Cortex repository folder when prompted. From **Project Workspace → Build & Run**, use the discovered runtime/build actions to build and launch Cortex.

The standalone PCC remains separate from the Cortex executable and repository, which makes it useful as a fallback when the in-project PCC surface itself is being repaired.


Update 0.10.3: moved health monitor into a persistent bottom status tray, added project health column on the Projects tab, and added Vault root mounting for drive-style onboarding.
