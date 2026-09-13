#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

ENVELOPE_VERSION = "FORGEPY-OPERATION-ENVELOPE-1.1-F568"
DEFAULT_EVENT_LIMIT = 2500


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class OperationEvent:
    operation_id: str
    project_id: str
    command: str
    event_type: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp_utc: str = field(default_factory=utc_now)
    sequence: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "forgepy.operation-event.v1", "version": ENVELOPE_VERSION, **asdict(self)}


class OperationTranscript:
    """Bounded in-memory operation transcript.

    Live emitters still receive every event as it happens. Only retained history is
    bounded, so a multi-hour build cannot grow ForgePY memory without limit.
    """

    def __init__(
        self,
        project_id: str,
        command: str,
        *,
        initiator: str = "forgepy",
        event_limit: int = DEFAULT_EVENT_LIMIT,
    ) -> None:
        self.operation_id = uuid.uuid4().hex
        self.project_id = project_id
        self.command = command
        self.initiator = initiator
        self.started = time.monotonic()
        self.event_limit = max(100, int(event_limit))
        self.events: deque[OperationEvent] = deque(maxlen=self.event_limit)
        self._sequence = 0
        self._dropped = 0

    def emit(self, event_type: str, message: str = "", **data: Any) -> OperationEvent:
        self._sequence += 1
        if len(self.events) >= self.event_limit:
            self._dropped += 1
        event = OperationEvent(
            self.operation_id,
            self.project_id,
            self.command,
            event_type,
            message,
            dict(data),
            sequence=self._sequence,
        )
        self.events.append(event)
        return event

    def finish(self, *, ok: bool, returncode: int = 0, result: Any = None, error: str = "") -> dict[str, Any]:
        elapsed = round((time.monotonic() - self.started) * 1000.0, 1)
        self.emit("operation.finished" if ok else "operation.failed", error if error else "", returncode=returncode)
        return {
            "schema": "forgepy.operation-transcript.v1",
            "version": ENVELOPE_VERSION,
            "operationId": self.operation_id,
            "projectId": self.project_id,
            "command": self.command,
            "initiator": self.initiator,
            "ok": bool(ok),
            "returncode": int(returncode),
            "elapsedMs": elapsed,
            "result": result,
            "error": error,
            "eventsRetained": len(self.events),
            "eventsDropped": self._dropped,
            "events": [event.to_dict() for event in self.events],
        }

    def stream_json(self) -> str:
        return "\n".join(json.dumps(event.to_dict(), sort_keys=True) for event in self.events)
