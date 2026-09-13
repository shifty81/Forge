# ForgePY F765 — egui 0.36 Windows Compile Repair

## Trigger

The first Windows compile of the F764 native GUI reached the pinned `egui 0.36.2` dependency set and failed in `native/forge-rs/src/gui/theme.rs` because the shell still used the older Context-wide `style()` and `set_style()` methods.

## Repair

F765 uses the egui 0.36 theme-aware Context API:

- `ctx.set_theme(Theme::Dark)`
- `ctx.style_of(Theme::Dark)`
- `ctx.set_style_of(Theme::Dark, style)`

No GUI behavior is intentionally changed beyond restoring the pinned dependency contract and forcing ForgePY's dark theme consistently.

## Certification

Python/static ForgePY gates can verify the source contract, but the authoritative native result is the Windows **Rust SHADOW Gate**, because this environment does not include Cargo/rustc. Run the SHADOW Gate after applying F765; if another Rust compiler error appears, treat that output as the next compile-compatibility repair input.
