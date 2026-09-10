# Vault architecture

Vault is the universal standalone project operations authority and the intended machine/tooling brain used by Cortex.

```text
Vault GUI / Console / future Cortex API
                |
        shared Vault spine
                |
  Project registry + discovery
  Vault Library/catalog + intake
  transactional patch/recovery
  operation host + process capture
  Health + Git/GitHub/Forgejo state
                |
        selected project adapter
                |
 existing project tooling / build system
```

Vault owns generic execution, evidence, intake and project intelligence. A project adapter owns only genuinely project-specific build/run/test semantics. Existing mature project utilities are consumed before generic commands are inferred.
