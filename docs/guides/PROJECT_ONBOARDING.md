# Project Onboarding

A project does not need to embed Forge. Register or choose its root and Forge scans for existing `project.control.json`, root utilities, Cargo, CMake, Gradle, Node, Python, Git, runtime commands and known PCC providers.

During migration Forge binds the strongest available project command authority. The long-term target is a thin project adapter/contract containing only project-specific build, run, test and special-tool semantics while Forge owns Git/GitHub/Forgejo, GREEN, patches, transactions, recovery, Vault and diagnostics universally.
