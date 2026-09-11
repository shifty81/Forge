# Forge F60R7 GUI Responsiveness and Windows Process Containment

F60R7 treats the GUI as a latency-sensitive shell. Background health, source and intake services must never allocate visible consoles and must not monopolize Tk's event loop.

## Policies

- Read/status probes use `CREATE_NO_WINDOW` + hidden startup info on Windows.
- Foreground project operations remain captured in Forge's embedded Project Console.
- Periodic health runs no more often than 30 seconds by default, never overlaps itself, and pauses while a foreground job is active or Forge is hidden.
- Full registered-project discovery/health is explicit Rescan work; project activation uses registry/cache state.
- GREEN source fingerprints are expensive and are cached until Git work-tree/HEAD/marker state changes.
- Tk event draining is time-budgeted; compiler output cannot starve mouse/paint events.
- Auto-scroll is throttled and hidden duplicate log views are not repainted.
- Forge restarts itself through Python/pythonw, not VBS, so Mark-of-the-Web on compatibility launchers cannot trigger the Windows Open File Security Warning.
- Forge-owned prompts are owned/transient modal tool windows and remain above their Forge parent without permanent system-topmost behavior.
