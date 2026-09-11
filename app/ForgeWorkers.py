#!/usr/bin/env python3
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, Future
import threading
from typing import Any, Callable
from ForgeEventBroker import EventBroker

WORKERS_VERSION = "FORGEPY-WORKERS-0.1"

class ForgeWorkerPool:
    def __init__(self, broker: EventBroker, max_workers: int=6) -> None:
        self.broker=broker
        self._pool=ThreadPoolExecutor(max_workers=max(2,int(max_workers)), thread_name_prefix='ForgePY')
        self._jobs: dict[str, Future[Any]]={}
        self._lock=threading.RLock()
    def submit(self, label: str, fn: Callable[[], Any], *, topic: str='worker.done') -> Future[Any]:
        label=str(label)
        def run():
            self.broker.publish('worker.started', {'label':label})
            try:
                result=fn(); self.broker.publish(topic, {'label':label,'ok':True,'result':result}); return result
            except Exception as exc:
                self.broker.publish(topic, {'label':label,'ok':False,'error':str(exc)}); raise
            finally:
                with self._lock: self._jobs.pop(label,None)
        future=self._pool.submit(run)
        with self._lock: self._jobs[label]=future
        return future
    def active(self) -> tuple[str,...]:
        with self._lock: return tuple(k for k,v in self._jobs.items() if not v.done())
    def shutdown(self) -> None: self._pool.shutdown(wait=False, cancel_futures=True)
