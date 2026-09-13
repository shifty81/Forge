# ForgePY F701-F740 — Executable / Installer / Application Update System

## Executable authority

ForgePY's Windows executable authority is Nuitka standalone/onedir.

The build lane:
1. validates Windows, icon, bootstrap and Nuitka;
2. performs a clean standalone build;
3. explicitly includes flat `app/*.py` modules used through runtime/dynamic hooks;
4. produces `dist/ForgePY/ForgePY.exe` plus companion files;
5. derives an Installed Image and Portable Image;
6. produces a portable ZIP;
7. produces a `.forgeupdate` application-image update bundle;
8. generates the Inno Setup installer script;
9. builds the installer automatically when Inno Setup 6 is available.

## Installer choices

The generated Setup executable offers:

- Standard install — application files under LocalAppData Programs and mutable ForgePY state in AppData.
- Portable install — selected directory with `.forgepy-portable`; ForgePY creates/preserves local `Data`.

Portable selection does not create normal Start Menu/Desktop shortcuts or an uninstall registration.

## Application update transport

Once ForgePY is compiled, Python source `.patch` files cannot directly mutate compiled modules.
The executable distribution therefore emits a `*.forgeupdate` bundle containing:

- update manifest;
- version/build;
- exact application-image file list;
- SHA-256 for every application file;
- complete replacement onedir image.

The same ForgePY Settings workflow queues both development source transports and packaged
application updates, but installed ForgePY.exe promotes only the validated `.forgeupdate` image.

## Transactional self-update

Staging and rollback are intentionally outside the application directory being replaced.

Standard:
- application: LocalAppData Programs
- update state/staging/rollback: LocalAppData ForgePY application-maintenance area

Portable:
- application: selected portable ForgePY directory
- mutable state: `<install>/Data`
- application staging/rollback: sibling `.ForgePY.ForgePYMaintenance` area
- promotion preserves/moves the old `Data` directory into the new application image

Promotion helper is generated in the system temp directory, waits for ForgePY.exe to exit,
swaps the complete application directory, restores portable Data, restarts ForgePY.exe, and
restores the previous directory if the swap itself fails.

## Rapid-navigation hardening

Packaging alone does not solve Tk event-loop stalls. F740 also changes navigation behavior:

- rapid app-tab clicks are debounced/latest-request-wins;
- duplicate requests for the already visible surface are no-ops;
- failed lazy surface builds restore the last stable frame;
- quick-bar rows are constructed completely before replacing the previous row, preventing
  disappearing toolbar buttons during rapid navigation;
- navigation commit duration is sent to ForgePY performance telemetry.

## Future Rust client

A Rust client can improve rendering/input responsiveness substantially, but only if it replaces
the Tk presentation layer. Wrapping the same Tk GUI in a Rust launcher would not solve Tk stalls.

The intended future seam is:
Rust native shell → local IPC/JSON stream → ForgePY canonical operation/project services.

Python remains the project/Vault/patch/source authority until the Rust implementation achieves
verified parity and is explicitly approved for takeover. Do not create a second workflow model.
