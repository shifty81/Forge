# F777 Update-State / Windows Gate Stabilization

F777 fixes three live-Windows integration seams discovered while moving from F766 to F776.

1. `native/forge-rs/Cargo.lock` remains runtime-transient during SHADOW. Cargo may materialize it; quality gates verify governance classification rather than demanding physical absence.
2. Fallback debug bundle creation imports all required stdlib helpers and can actually write the ZIP after a failed gate.
3. Downloads discovery is operation-aware. If an approved update is queued, being applied, or applied and awaiting restart, ForgePY reports that state instead of presenting the misleading “No compatible candidate” message.

The F776 native GUI and Project Intelligence code is otherwise unchanged.
