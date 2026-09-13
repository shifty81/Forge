# ForgePY Tool Activation Contract

A discovered file is not an integrated tool. ForgePY promotes tooling through:

`DISCOVERED -> CLASSIFIED -> PROBED -> READY/EXECUTABLE -> VERIFIED`

`BLOCKED` is explicit and includes the reason (missing interpreter/toolchain or unsupported execution type).

Authority order:
1. project.control.json / project-owned PCC or CLI;
2. project-declared tool registry;
3. verified machine-local generated adapter;
4. generic build/language adapter;
5. operator mapping.

Tool scopes are `global`, `project`, and `project-family`. Generated adapters are stored under the machine Vault and never silently modify project source.

An activated tool records owner project, executable/interpreter, arguments, working directory, capability, category, mutation/destructive flags, state and provenance. ForgePY's runtime streams stdout/stderr to Project Console and returns an exit-code receipt. Mutating tools require operator confirmation in the GUI.
