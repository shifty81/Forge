#!/usr/bin/env python3
from __future__ import annotations

import json
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

PERFORMANCE_VERSION = "FORGEPY-PERF-0.1"
_LOCK = threading.Lock()
_EVENTS: deque["PerfEvent"] = deque(maxlen=256)


@dataclass(frozen=True)
class PerfEvent:
    name: str
    elapsed_ms: float
    threshold_ms: float
    slow: bool
    timestamp: float


def record(name: str, elapsed_ms: float, threshold_ms: float = 100.0) -> PerfEvent:
    event = PerfEvent(str(name), float(elapsed_ms), float(threshold_ms), float(elapsed_ms) >= float(threshold_ms), time.time())
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
