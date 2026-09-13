# ForgePY F60R373 — Silent-exit hotfix

The F60R372 GUI launcher could legitimately return exit code 0 before building the main GUI when the project registry had no usable active project. Normal startup called the folder-picker path; a cancelled/unavailable selection returned `None`, and `main()` immediately returned. Because the preferred VBS launcher used pythonw with no console, this looked exactly like ForgePY launching and closing itself.

F60R373 removes project selection as a prerequisite for normal shell startup. It falls back to the most recently opened valid project, then to ForgePY's own project contract. The GUI therefore remains available so project selection can happen from the Projects surface.

The VBS launcher also waits invisibly for the application and displays a diagnostic dialog for a nonzero exit. Python startup exceptions are written to crash diagnostics and surfaced visibly.
