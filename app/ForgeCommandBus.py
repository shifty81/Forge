#!/usr/bin/env python3
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from ForgeProjectProtocol import normalize_key

COMMAND_BUS_VERSION = "FORGEPY-COMMAND-BUS-3.0-F467"


@dataclass(frozen=True)
class CommandSpec:
    key: str
    handler: Callable[..., Any]
    category: str = ""
    mutates: bool = False
    description: str = ""
    owner: str = "forgepy"
    label: str = ""
    risk: str = "read"
    aliases: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    supports_streaming: bool = True
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class CommandResult:
    key: str
    ok: bool
    value: Any = None
    error: str = ""
    canonical_key: str = ""


class CommandBus:
    def __init__(self) -> None:
        self._handlers: dict[str, CommandSpec] = {}
        self._aliases: dict[str, str] = {}
        self._lock = threading.RLock()

    def register(
        self,
        key: str,
        handler: Callable[..., Any],
        *,
        replace: bool = False,
        category: str = "",
        mutates: bool = False,
        description: str = "",
        owner: str = "forgepy",
        label: str = "",
        risk: str = "read",
        aliases: tuple[str, ...] = (),
        requires: tuple[str, ...] = (),
        supports_streaming: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        canonical = normalize_key(key)
        spec = CommandSpec(
            canonical, handler, category, bool(mutates), description, owner,
            label or canonical, risk, tuple(aliases), tuple(requires),
            bool(supports_streaming), dict(metadata or {}),
        )
        with self._lock:
            if canonical in self._handlers and not replace:
                raise KeyError(canonical)
            self._handlers[canonical] = spec
            self._aliases[canonical.casefold()] = canonical
            self._aliases[str(key).casefold()] = canonical
            for alias in aliases:
                self._aliases[str(alias).casefold()] = canonical

    def unregister(self, key: str) -> bool:
        with self._lock:
            canonical = self._aliases.get(str(key).casefold(), normalize_key(key))
            removed = self._handlers.pop(canonical, None)
            if removed is None:
                return False
            for alias, target in tuple(self._aliases.items()):
                if target == canonical:
                    self._aliases.pop(alias, None)
            return True

    def resolve_key(self, key: str) -> str:
        with self._lock:
            return self._aliases.get(str(key).casefold(), normalize_key(key))

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._handlers))

    def specs(self) -> tuple[CommandSpec, ...]:
        with self._lock:
            return tuple(self._handlers[k] for k in sorted(self._handlers))

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "key": s.key, "label": s.label, "category": s.category,
                "mutates": s.mutates, "risk": s.risk, "description": s.description,
                "owner": s.owner, "aliases": list(s.aliases), "requires": list(s.requires),
                "supportsStreaming": s.supports_streaming, "metadata": dict(s.metadata),
            }
            for s in self.specs()
        ]

    def execute(self, key: str, *args: Any, **kwargs: Any) -> CommandResult:
        canonical = self.resolve_key(key)
        with self._lock:
            spec = self._handlers.get(canonical)
        if spec is None:
            return CommandResult(str(key), False, error="command not registered", canonical_key=canonical)
        try:
            return CommandResult(str(key), True, value=spec.handler(*args, **kwargs), canonical_key=canonical)
        except Exception as exc:
            return CommandResult(str(key), False, error=str(exc), canonical_key=canonical)
