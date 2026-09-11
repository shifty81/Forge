#!/usr/bin/env python3
from __future__ import annotations
import queue, threading, time
from dataclasses import dataclass
from typing import Any, Callable

BROKER_VERSION = "FORGEPY-EVENT-BROKER-0.1"

@dataclass(frozen=True)
class ForgeEvent:
    topic: str
    payload: Any
    created: float

class EventBroker:
    def __init__(self) -> None:
        self._q: queue.Queue[ForgeEvent] = queue.Queue()
        self._subs: dict[str, list[Callable[[ForgeEvent], None]]] = {}
        self._lock = threading.RLock()
    def publish(self, topic: str, payload: Any=None) -> None:
        self._q.put(ForgeEvent(str(topic), payload, time.time()))
    def subscribe(self, topic: str, callback: Callable[[ForgeEvent], None]) -> None:
        with self._lock: self._subs.setdefault(str(topic), []).append(callback)
    def drain(self, limit: int=256) -> list[ForgeEvent]:
        out=[]
        for _ in range(max(1, int(limit))):
            try: event=self._q.get_nowait()
            except queue.Empty: break
            out.append(event)
            with self._lock:
                callbacks=[*self._subs.get(event.topic,()), *self._subs.get('*',())]
            for callback in callbacks:
                try: callback(event)
                except Exception: pass
        return out
    def pending(self) -> int: return self._q.qsize()
