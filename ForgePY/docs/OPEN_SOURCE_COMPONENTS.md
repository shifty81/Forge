# Vault Open-Source Component Policy

Vault's standalone Tk recovery/control surface has no mandatory third-party Python package requirement. Optional components are installed only when a feature benefits from them and each component is recorded with its license.

## Approved optional components

| Component | License | Vault role |
| --- | --- | --- |
| Monaco Editor | MIT | Vault IDE pop-out editor |
| pywebview | BSD-3-Clause | Separate Windows WebView2 host for Monaco |
| watchfiles | MIT | Event-driven filesystem monitoring candidate |
| Tree-sitter / py-tree-sitter | MIT | Incremental source parsing and symbol intelligence candidate |
| ripgrep | MIT OR Unlicense | Fast Search Everywhere / project text search candidate |
| psutil | BSD-3-Clause | Service/process/host health metrics candidate |

## Adoption order

1. Keep current polling watcher as guaranteed fallback; add `watchfiles` as an optional acceleration layer.
2. Add `ripgrep` for Search Everywhere and tooling/source discovery, while retaining a Python fallback.
3. Add Tree-sitter for symbol extraction, language-aware indexing and IDE navigation.
4. Add psutil for service/process health, resource pressure and diagnostics.
5. Move Monaco runtime loading from its compatibility loader to a Vault-owned ESM bundle without changing the Python IDE RPC contract.
6. Add optional language servers behind Vault/Cortex capability contracts rather than embedding language-specific logic into the GUI.

No optional component may become necessary to run Full Gate, inspect a project, recover an update, use source control or reach the native editor.
