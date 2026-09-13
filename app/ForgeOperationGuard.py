#!/usr/bin/env python3
from __future__ import annotations
import threading, time, uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

OPERATION_GUARD_VERSION = "FORGEPY-OPERATION-GUARD-1.0-F604"

@dataclass(frozen=True)
class Lease:
    token: str
    project_id: str
    command: str
    started: float

class OperationGuard:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active: dict[tuple[str, str], Lease] = {}
        self._last_finish: dict[tuple[str, str], float] = {}

    def acquire(self, project_id: str, command: str, *, cooldown: float = 0.0) -> Lease | None:
        key = (str(project_id).casefold(), str(command).casefold())
        now = time.monotonic()
        with self._lock:
            if key in self._active:
                return None
            last = self._last_finish.get(key, 0.0)
            if cooldown > 0 and now - last < cooldown:
                return None
            lease = Lease(uuid.uuid4().hex, project_id, command, now)
            self._active[key] = lease
            return lease

    def release(self, lease: Lease) -> None:
        key = (lease.project_id.casefold(), lease.command.casefold())
        with self._lock:
            current = self._active.get(key)
            if current is not None and current.token == lease.token:
                self._active.pop(key, None)
                self._last_finish[key] = time.monotonic()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": "forgepy.operation-guard.v1",
                "version": OPERATION_GUARD_VERSION,
                "active": [lease.__dict__ for lease in self._active.values()],
            }

    @contextmanager
    def hold(self, project_id: str, command: str, *, cooldown: float = 0.0) -> Iterator[Lease]:
        lease = self.acquire(project_id, command, cooldown=cooldown)
        if lease is None:
            raise RuntimeError(f"operation already active or cooling down: {project_id}:{command}")
        try:
            yield lease
        finally:
            self.release(lease)

GUARD = OperationGuard()
