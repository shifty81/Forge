#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

PATCH_VERSION = "FORGEPY-BACKEND-CAPABILITY-PATCH-F567"


def install() -> bool:
    try:
        from PCCSurfaceCommon import BackendClient
        from ForgeProjectProtocol import aliases_for, normalize_key
    except Exception:
        return False

    if getattr(BackendClient, "_forge_protocol_supports_installed_f567", False):
        return True

    original_supports = BackendClient.supports
    original_status = BackendClient.status

    def supports(self: Any, command: str) -> bool:
        requested = str(command or "").strip()
        if not requested:
            return False
        if requested == "status-json":
            return True

        # ForgePY's explicit update boundary is universal. The operation host can
        # apply a ForgePY transport without a project-native patch command.
        if requested in {"patch-apply", "patch.apply", "patch.apply-staged"}:
            return True

        keys = {str(item.key).casefold() for item in getattr(self.contract, "commands", ())}
        canonical = normalize_key(requested)
        candidates = {requested.casefold(), canonical.casefold()}
        candidates.update(alias.casefold() for alias in aliases_for(canonical))
        if keys & candidates:
            return True

        if getattr(self, "provider_mode", "") == "forgepy-adapter":
            adapter = getattr(self, "_generated_adapter", {}) or {}
            caps = {str(value).casefold() for value in (adapter.get("capabilities") or {}).keys()}
            return bool(caps & candidates)

        # A native Python implementation is not proof that every arbitrary command
        # exists. Keep capability advertisement conservative unless discovery/contract
        # metadata declared it. This prevents GUI/CLI buttons from lying.
        if getattr(self, "provider_mode", "") == "python":
            return False

        try:
            return bool(original_supports(self, requested))
        except Exception:
            return False

    def status(self: Any) -> dict[str, Any]:
        mode = str(getattr(self, "provider_mode", "") or "")
        # Auto-contract and generated ForgePY adapters ultimately call the generic
        # PCCAutoAdapter status path. Avoid spawning a child interpreter just to read
        # the same generic status snapshot. Native project providers remain authoritative.
        if mode in {"auto-contract", "forgepy-adapter"}:
            try:
                from ForgeStatusCache import fast_auto_status_payload
                return fast_auto_status_payload(self.root)
            except Exception:
                pass
        return original_status(self)

    BackendClient.supports = supports
    BackendClient.status = status
    BackendClient._forge_protocol_supports_installed = True
    BackendClient._forge_protocol_supports_installed_f567 = True
    return True
