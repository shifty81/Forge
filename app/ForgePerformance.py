#!/usr/bin/env python3
from __future__ import annotations

import json
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

PERFORMANCE_VERSION = "FORGEPY-PERF-0.2"
_LOCK = threading.Lock()
_EVENTS: deque["PerfEvent"] = deque(maxlen=256)


@dataclass(frozen=True)
class PerfEvent:
    name: str
    elapsed_ms: float
    threshold_ms: float
    slow: bool
    timestamp: float
    metadata: dict[str, Any] | None = None


def record(
    name: str,
    elapsed_ms: float,
    threshold_ms: float | dict[str, Any] = 100.0,
    metadata: dict[str, Any] | None = None,
) -> PerfEvent:
    # Compatibility hardening: F60R372 accidentally passed metadata as the
    # third positional argument. Treat a mapping there as metadata rather than
    # attempting float(dict), which crashed the GUI during initial project refresh.
    if isinstance(threshold_ms, dict):
        if metadata is None:
            metadata = dict(threshold_ms)
        threshold_value = 100.0
    else:
        threshold_value = float(threshold_ms)

    elapsed_value = float(elapsed_ms)
    event = PerfEvent(
        str(name),
        elapsed_value,
        threshold_value,
        elapsed_value >= threshold_value,
        time.time(),
        dict(metadata) if metadata else None,
    )
    with _LOCK:
        _EVENTS.append(event)
    return event


@contextmanager
def measure(name: str, threshold_ms: float = 100.0) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        record(name, (time.perf_counter() - start) * 1000.0, threshold_ms)


def recent(limit: int = 100, *, slow_only: bool = False) -> list[dict[str, object]]:
    with _LOCK:
        rows = list(_EVENTS)
    if slow_only:
        rows = [x for x in rows if x.slow]
    return [asdict(x) for x in rows[-max(1, int(limit)):]]


def export(path: Path, limit: int = 256) -> Path:
    payload = {"schema": "forgepy.performance.v1", "version": PERFORMANCE_VERSION, "events": recent(limit)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


class UiLagProbe:
    def __init__(self, expected_ms: float=100.0, threshold_ms: float=180.0) -> None:
        self.expected_ms=expected_ms; self.threshold_ms=threshold_ms; self._last=time.perf_counter()
    def tick(self) -> PerfEvent:
        now=time.perf_counter(); elapsed=(now-self._last)*1000.0; self._last=now
        lag=max(0.0,elapsed-self.expected_ms); return record("ui-event-loop-lag",lag,self.threshold_ms)
