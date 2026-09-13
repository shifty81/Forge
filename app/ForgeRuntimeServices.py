#!/usr/bin/env python3
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

from ForgeActivity import append as activity_append
from ForgeCommandBus import CommandBus
from ForgeEventBroker import EventBroker
from ForgeJobs import JobQueue
from ForgeProvenance import append as provenance_append
from ForgeReceipts import write as receipt_write
from ForgeStateBroker import ProjectStateBroker
from ForgeWorkers import ForgeWorkerPool
from ForgeOperationEnvelope import OperationTranscript

RUNTIME_SERVICES_VERSION = "FORGEPY-RUNTIME-SERVICES-2.1-F620"


class ForgeRuntimeServices:
    """Single application-owned execution/event spine for GUI, CLI, Cortex and automation."""

    def __init__(self, *, max_workers: int = 6) -> None:
        self.events = EventBroker()
        self.state = ProjectStateBroker()
        self.commands = CommandBus()
        self.jobs = JobQueue(max_workers=max(2, int(max_workers)))
        self.workers = ForgeWorkerPool(self.events, max_workers=max_workers)
        self._lock = threading.RLock()
        self._active: dict[str, dict[str, Any]] = {}
        self._transcripts: dict[str, OperationTranscript] = {}

    def operation_started(self, project_id: str, key: str, **metadata: Any) -> str:
        transcript = OperationTranscript(project_id, key, initiator=str(metadata.get("initiator") or "forgepy"))
        token = transcript.operation_id
        row = {"token": token, "projectId": project_id, "key": key, "started": time.time(), **metadata}
        transcript.emit("operation.started", key, metadata=metadata)
        with self._lock:
            self._active[token] = row
            self._transcripts[token] = transcript
        self.state.update(project_id, activeOperation=key, activeOperationToken=token)
        activity_append("operation.started", project_id, key=key, token=token, metadata=metadata)
        provenance_append("operation.started", project_id, key=key, token=token)
        self.events.publish("operation.started", row)
        return token

    def operation_event(self, token: str, event_type: str, message: str = "", **data: Any) -> dict[str, Any] | None:
        with self._lock:
            transcript = self._transcripts.get(token)
            row = self._active.get(token)
        if transcript is None or row is None:
            return None
        event = transcript.emit(event_type, message, **data)
        payload = event.to_dict()
        self.events.publish("operation.event", payload)
        activity_append("operation.event", str(row["projectId"]), key=row["key"], token=token, event=payload)
        return payload

    def operation_finished(self, token: str, *, ok: bool, result: Any = None, error: str = "") -> Path | None:
        with self._lock:
            row = self._active.pop(token, None)
            transcript = self._transcripts.pop(token, None)
        if row is None:
            return None
        elapsed_ms = round((time.time() - float(row["started"])) * 1000.0, 1)
        project_id = str(row["projectId"])
        payload = {
            "key": row["key"], "ok": bool(ok), "elapsedMs": elapsed_ms,
            "result": result if isinstance(result, (str, int, float, bool, dict, list, type(None))) else repr(result),
            "error": str(error or ""),
        }
        if transcript is not None:
            payload["transcript"] = transcript.finish(ok=ok, returncode=0 if ok else 1, result=payload["result"], error=payload["error"])
        self.state.update(project_id, activeOperation="", activeOperationToken="", lastOperation=payload)
        activity_append("operation.finished", project_id, **payload)
        provenance_append("operation.finished", project_id, **payload)
        receipt = receipt_write(project_id, "operations", payload)
        self.events.publish("operation.finished", {"projectId": project_id, "receipt": str(receipt), **payload})
        return receipt

    def submit(self, project_id: str, label: str, fn: Callable[[], Any], *, initiator: str = "forgepy"):
        token = self.operation_started(project_id, label, initiator=initiator)
        def wrapped():
            try:
                value = fn()
                self.operation_finished(token, ok=True, result=value)
                return value
            except Exception as exc:
                self.operation_finished(token, ok=False, error=str(exc))
                raise
        return self.workers.submit(f"{project_id}:{label}", wrapped)


    def run_canonical(
        self,
        root: Path,
        command: str,
        *,
        extra: list[str] | None = None,
        initiator: str = "runtime",
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Delegate to ForgePY's canonical operation service; never fork Cortex policy."""
        from ForgeUnifiedServices import operations

        def forward(event: dict[str, Any]) -> None:
            self.events.publish("operation.event", event)
            if emit is not None:
                emit(event)

        result = operations.run(root, command, extra=extra, initiator=initiator, emit=forward)
        project_id = str(result.get("projectId") or "")
        if project_id:
            self.state.update(project_id, lastCanonicalOperation=result)
        return result

    def command_catalog(self) -> list[dict[str, Any]]:
        return self.commands.describe()

    def active_operations(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._active.values()]

    def shutdown(self) -> None:
        self.workers.shutdown()
