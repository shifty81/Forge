#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ForgeVaultBootstrap import layout

JOBS_VERSION = "FORGEPY-JOBS-2.1-F551"
_MAX_HISTORY = 500


@dataclass
class Job:
    job_id: str
    label: str
    project_id: str = ""
    state: str = "QUEUED"
    created: float = field(default_factory=time.time)
    started: float = 0.0
    finished: float = 0.0
    result: Any = None
    error: str = ""
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)


class JobQueue:
    def __init__(self, max_workers: int = 4) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max(1, int(max_workers)), thread_name_prefix="ForgeJob")
        self._jobs: dict[str, Job] = {}
        self._futures: dict[str, Future[Any]] = {}
        self._lock = threading.RLock()
        self._persist_lock = threading.Lock()
        self._project_locks: dict[str, threading.Lock] = {}

    def _prune_locked(self) -> None:
        if len(self._jobs) <= _MAX_HISTORY:
            return
        complete = [
            job for job in self._jobs.values()
            if job.state in {"PASS", "FAIL", "CANCELLED"} and job.finished
        ]
        complete.sort(key=lambda job: (job.finished, job.created))
        remove_count = max(0, len(self._jobs) - _MAX_HISTORY)
        for job in complete[:remove_count]:
            self._jobs.pop(job.job_id, None)
            self._futures.pop(job.job_id, None)

    def submit(self, label: str, fn: Callable[[threading.Event], Any], project_id: str = "") -> Job:
        job = Job(uuid.uuid4().hex, str(label), str(project_id))
        with self._lock:
            self._jobs[job.job_id] = job
            lock = self._project_locks.setdefault(project_id, threading.Lock()) if project_id else threading.Lock()
            self._prune_locked()

        def run() -> Any:
            job.started = time.time()
            job.state = "RUNNING"
            self.persist()
            try:
                with lock:
                    if job.cancel.is_set():
                        job.state = "CANCELLED"
                        return None
                    job.result = fn(job.cancel)
                    job.state = "CANCELLED" if job.cancel.is_set() else "PASS"
                    return job.result
            except Exception as exc:
                job.error = str(exc)
                job.state = "FAIL"
                raise
            finally:
                job.finished = time.time()
                with self._lock:
                    # Keep the completed Future addressable while the Job remains in bounded history.
                    # This avoids a completion race for callers waiting on q._futures[job_id].
                    self._prune_locked()
                self.persist()

        future = self._pool.submit(run)
        with self._lock:
            self._futures[job.job_id] = future
        self.persist()
        return job

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.cancel.set()
            if job.state == "QUEUED":
                job.state = "CANCELLED"
                job.finished = time.time()
            self._prune_locked()
        self.persist()
        return True

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._jobs.values())
        out: list[dict[str, Any]] = []
        for job in rows:
            result = job.result if isinstance(job.result, (str, int, float, bool, dict, list, type(None))) else repr(job.result)
            out.append({
                "job_id": job.job_id,
                "label": job.label,
                "project_id": job.project_id,
                "state": job.state,
                "created": job.created,
                "started": job.started,
                "finished": job.finished,
                "result": result,
                "error": job.error,
                "cancelRequested": job.cancel.is_set(),
            })
        return out

    def persist(self) -> Path:
        path = layout()["state"] / "jobs.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "forgepy.jobs.v2",
            "version": JOBS_VERSION,
            "jobs": self.snapshot(),
        }
        encoded = json.dumps(payload, indent=2, default=str) + "\n"
        with self._persist_lock:
            temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
            temp.write_text(encoded, encoding="utf-8")
            os.replace(temp, path)
        return path

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
