# Forge Native F798-F807 — Self-Update Foundation (F797 Donor Baseline)

## Status

This is a **Rust-lane-only continuation** on top of the certified/public ForgePY F797 donor baseline.
ForgePY remains at `FORGEPY-F797`; the native identity also remains the F797 SHADOW identity until this
new Rust wave passes the real Windows Rust SHADOW gate. The patch deliberately does not advance Python
application identity or claim native takeover.

## Goal

Establish the packaged Forge Native update contract needed for the eventual portable/installed Rust app to
update itself using the same high-level model already proven by ForgePY:

1. receive a complete application-image update transport;
2. validate and stage it **outside** the live application directory;
3. wait for the running executable to exit;
4. atomically promote the staged application directory;
5. preserve portable mutable `Data`;
6. restart the new executable;
7. restore the previous application directory if promotion fails.

## New Rust authority

`native/forge-rs/src/update.rs` adds:

- `Development`, `Portable`, and `Installed` layout detection;
- `.forge-portable` plus legacy `.forgepy-portable` recognition;
- maintenance/staging roots that are outside the live application image;
- fail-closed transport classification;
- typed native update plans;
- Windows PowerShell directory-swap/rollback helper generation;
- portable `Data` preservation;
- update status, build, stage, and stage+arm CLI paths.

New native CLI probes/actions:

```text
ForgeNative.exe --update-status-json
ForgeNative.exe --root <ForgePY-root> --build-native-update <image-dir> --update-output <file.forgeupdate>
ForgeNative.exe --root <ForgePY-root> --stage-native-update <file.forgeupdate>
ForgeNative.exe --root <ForgePY-root> --stage-and-arm-native-update <file.forgeupdate>
```

`--stage-and-arm-native-update` intentionally refuses development/Cargo-target layouts. A live Cargo
workspace must never be replaced as if it were a packaged installation.

## SHADOW verification bridge

`tools/rust/ForgeNativeUpdateBridge.py` is temporary SHADOW infrastructure. It owns the archive/hash side
of this wave while the Rust implementation is still being certified:

- native update schema: `forge.native.application-update.v1`;
- manifest: `FORGE_NATIVE_UPDATE_MANIFEST.json`;
- application payload root: `image/`;
- complete governed file list;
- SHA-256 and exact byte count for every file;
- no traversal, absolute paths, symbolic links, duplicates, undeclared payloads, or missing payloads;
- bounded file count and extraction size;
- staging outside the live application root;
- persisted `current-plan.json` evidence.

The bridge can also build the same native `.forgeupdate` bundle from a prepared application image. This is
not the final architecture: archive parsing/hash verification should move natively into Rust after the
Windows gate proves this contract and packaging layout.

## Update manifest

Example:

```json
{
  "schema": "forge.native.application-update.v1",
  "bridgeVersion": "FORGE-NATIVE-UPDATE-BRIDGE-1.0-F807",
  "applicationVersion": "0.5.0-shadow",
  "applicationBuild": "FORGE-NATIVE-PCC-ASSET-BRIDGE-0.7.0-F797",
  "entrypoint": "ForgeNative.exe",
  "files": [
    {
      "path": "ForgeNative.exe",
      "bytes": 123456,
      "sha256": "..."
    }
  ]
}
```

## Why native identity is not bumped yet

The container used to produce this overwrite package does not have Cargo/rustc. Python bridge tests are
GREEN, but Rust compilation must be proven on the user's Windows toolchain. Keeping the currently certified
F797 native build identity avoids pretending an uncompiled candidate is already certified.

After the Windows Rust SHADOW gate passes, the next patch should:

1. advance the native build identity;
2. package `ForgeNative.exe` into explicit installed/portable images;
3. expose update readiness/staging in the native GUI Updates panel;
4. wire the internal PCC to native update build/stage certification commands;
5. replace the Python archive/hash bridge with Rust ZIP + SHA-256 authority;
6. add signed update provenance and post-restart certification/automatic rollback.

## Overwrite application

This package is rooted at the Forge repository root. Close the running native Forge window, extract the ZIP
directly over the current **F797** Forge repository, allow overwrite/merge, then run the normal internal
ForgePY Full Gate / Rust SHADOW gate. No manual patch engine is required for this temporary Rust-lane
bootstrap step.
