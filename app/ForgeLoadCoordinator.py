#!/usr/bin/env python3
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator

COORDINATOR_VERSION = "FORGEPY-LOAD-COORDINATOR-1.2-F620"


@dataclass(frozen=True)
class LoadSnapshot:
    interactive_depth: int
    active_scan: str
    scan_started: float
    last_interaction: float


class LoadCoordinator:
    """Serialize disk-heavy background work and protect interactive GUI actions.

    This is deliberately process-local. It does not own project policy; it only prevents
    independent recursive scanners from thrashing the same disk while the operator is trying
    to switch projects or navigate ForgePY.
    """

    def __init__(self) -> None:
        self._state = threading.Condition(threading.RLock())
        self._scan_lock = threading.Lock()
        self._interactive_depth = 0
        self._active_scan = ""
        self._scan_started = 0.0
        self._last_interaction = time.monotonic()

    def mark_interaction(self) -> None:
        with self._state:
            self._last_interaction = time.monotonic()
            self._state.notify_all()

    @contextmanager
    def interactive(self, label: str = "interactive") -> Iterator[None]:
        del label
        with self._state:
            self._interactive_depth += 1
            self._last_interaction = time.monotonic()
            self._state.notify_all()
        try:
            yield
        finally:
            with self._state:
                self._interactive_depth = max(0, self._interactive_depth - 1)
                self._last_interaction = time.monotonic()
                self._state.notify_all()

    def interactive_recent(self, seconds: float = 8.0) -> bool:
        with self._state:
            return self._interactive_depth > 0 or (time.monotonic() - self._last_interaction) < max(0.0, float(seconds))

    def scan_busy(self) -> bool:
        with self._state:
            return bool(self._active_scan)

    @contextmanager
    def scan(self, label: str, *, wait_for_idle: float = 2.0) -> Iterator[None]:
        # Background work waits briefly for interactive work to clear before competing for I/O.
        idle_budget = max(0.0, float(wait_for_idle))
        deadline = time.monotonic() + idle_budget
        with self._state:
            while self._interactive_depth > 0:
                self._state.wait(timeout=0.05)
            while time.monotonic() < deadline:
                recent = (time.monotonic() - self._last_interaction) < idle_budget if idle_budget else False
                if not recent:
                    break
                self._state.wait(timeout=0.05)
        self._scan_lock.acquire()
        with self._state:
            while self._interactive_depth > 0:
                self._state.wait(timeout=0.05)
        try:
            with self._state:
                self._active_scan = str(label)
                self._scan_started = time.monotonic()
            yield
        finally:
            with self._state:
                self._active_scan = ""
                self._scan_started = 0.0
                self._state.notify_all()
            self._scan_lock.release()

    def run_scan(self, label: str, fn: Callable[[], Any], *, wait_for_idle: float = 2.0) -> Any:
        with self.scan(label, wait_for_idle=wait_for_idle):
            return fn()

    def try_background_scan(self, label: str, fn: Callable[[], Any], *, idle_seconds: float = 8.0) -> tuple[bool, Any]:
        """Run only when ForgePY has been idle and no other coordinated scan owns the lane."""
        if self.interactive_recent(idle_seconds):
            return False, None
        if not self._scan_lock.acquire(blocking=False):
            return False, None
        try:
            with self._state:
                self._active_scan = str(label)
                self._scan_started = time.monotonic()
            return True, fn()
        finally:
            with self._state:
                self._active_scan = ""
                self._scan_started = 0.0
                self._state.notify_all()
            self._scan_lock.release()

    def snapshot(self) -> dict[str, Any]:
        with self._state:
            row = LoadSnapshot(
                self._interactive_depth,
                self._active_scan,
                self._scan_started,
                self._last_interaction,
            )
        return {
            "schema": "forgepy.load-coordinator.v1",
            "version": COORDINATOR_VERSION,
            "interactiveDepth": row.interactive_depth,
            "activeScan": row.active_scan,
            "activeScanSeconds": round(max(0.0, time.monotonic() - row.scan_started), 3) if row.scan_started else 0.0,
            "idleSeconds": round(max(0.0, time.monotonic() - row.last_interaction), 3),
        }


COORDINATOR = LoadCoordinator()
