#!/usr/bin/env python3
from __future__ import annotations
import threading, time
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

RUNTIME_SERVICES_VERSION = "FORGEPY-RUNTIME-SERVICES-1.0"

class ForgeRuntimeServices:
    """One application-owned integration point for shared ForgePY services.

    This deliberately keeps GUI code thin: operations publish lifecycle events,
    state and receipts here instead of each view inventing its own storage/threading.
    """
    def __init__(self, *, max_workers: int = 6) -> None:
        self.events = EventBroker()
        self.state = ProjectStateBroker()
        self.commands = CommandBus()
        self.jobs = JobQueue(max_workers=max(2, int(max_workers)))
        self.workers = ForgeWorkerPool(self.events, max_workers=max_workers)
        self._lock = threading.RLock()
        self._active: dict[str, dict[str, Any]] = {}

    def operation_started(self, project_id: str, key: str, **metadata: Any) -> str:
        token = f"{project_id}:{key}:{time.time_ns()}"
        row = {"token": token, "projectId": project_id, "key": key, "started": time.time(), **metadata}
        with self._lock:
            self._active[token] = row
        self.state.update(project_id, activeOperation=key, activeOperationToken=token)
        activity_append("operation.started", project_id, key=key, token=token, metadata=metadata)
        provenance_append("operation.started", project_id, key=key, token=token)
        self.events.publish("operation.started", row)
        return token

    def operation_finished(self, token: str, *, ok: bool, result: Any = None, error: str = "") -> Path | None:
        with self._lock:
            row = self._active.pop(token, None)
        if row is None:
            return None
        elapsed_ms = round((time.time() - float(row["started"])) * 1000.0, 1)
        project_id = str(row["projectId"])
        payload = {
            "key": row["key"], "ok": bool(ok), "elapsedMs": elapsed_ms,
            "result": result if isinstance(result, (str, int, float, bool, dict, list, type(None))) else repr(result),
            "error": str(error or ""),
        }
        self.state.update(project_id, activeOperation="", activeOperationToken="", lastOperation=payload)
        activity_append("operation.finished", project_id, **payload)
        provenance_append("operation.finished", project_id, **payload)
        receipt = receipt_write(project_id, "operations", payload)
        self.events.publish("operation.finished", {"projectId": project_id, "receipt": str(receipt), **payload})
        return receipt

    def submit(self, project_id: str, label: str, fn: Callable[[], Any]):
        token = self.operation_started(project_id, label)
        def wrapped():
            try:
                value = fn()
                self.operation_finished(token, ok=True, result=value)
                return value
            except Exception as exc:
                self.operation_finished(token, ok=False, error=str(exc))
                raise
        return self.workers.submit(f"{project_id}:{label}", wrapped)

    def shutdown(self) -> None:
        self.workers.shutdown()
