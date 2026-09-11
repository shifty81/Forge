#!/usr/bin/env python3
from __future__ import annotations
import json, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor,Future
from dataclasses import dataclass,field,asdict
from pathlib import Path
from typing import Any,Callable
from ForgeVaultBootstrap import layout

JOBS_VERSION='FORGEPY-JOBS-2.0'

@dataclass
class Job:
    job_id:str; label:str; project_id:str=''; state:str='QUEUED'
    created:float=field(default_factory=time.time); started:float=0.0; finished:float=0.0
    result:Any=None; error:str=''; cancel:threading.Event=field(default_factory=threading.Event, repr=False)

class JobQueue:
    def __init__(self,max_workers:int=4)->None:
        self._pool=ThreadPoolExecutor(max_workers=max(1,int(max_workers)),thread_name_prefix='ForgeJob')
        self._jobs:dict[str,Job]={}; self._futures:dict[str,Future]={}
        self._lock=threading.RLock(); self._project_locks:dict[str,threading.Lock]={}

    def submit(self,label:str,fn:Callable[[threading.Event],Any],project_id:str='')->Job:
        job=Job(uuid.uuid4().hex,label,project_id)
        with self._lock:
            self._jobs[job.job_id]=job
            lock=self._project_locks.setdefault(project_id,threading.Lock()) if project_id else threading.Lock()
        def run():
            job.started=time.time(); job.state='RUNNING'; self.persist()
            try:
                with lock:
                    if job.cancel.is_set(): job.state='CANCELLED'; return None
                    job.result=fn(job.cancel)
                    job.state='CANCELLED' if job.cancel.is_set() else 'PASS'
                    return job.result
            except Exception as exc:
                job.error=str(exc); job.state='FAIL'; raise
            finally:
                job.finished=time.time(); self.persist()
        fut=self._pool.submit(run)
        with self._lock:self._futures[job.job_id]=fut
        self.persist()
        return job

    def cancel(self,job_id:str)->bool:
        with self._lock:job=self._jobs.get(job_id)
        if not job:return False
        job.cancel.set()
        if job.state=='QUEUED': job.state='CANCELLED'
        self.persist(); return True

    def list(self)->list[Job]:
        with self._lock:return list(self._jobs.values())

    def snapshot(self)->list[dict[str,Any]]:
        out=[]
        for j in self.list():
            # Never call dataclasses.asdict() on Job: threading.Event contains a
            # native lock and deepcopy/pickle is invalid. Persist only durable fields.
            result=j.result if isinstance(j.result,(str,int,float,bool,dict,list,type(None))) else repr(j.result)
            out.append({
                'job_id':j.job_id,'label':j.label,'project_id':j.project_id,'state':j.state,
                'created':j.created,'started':j.started,'finished':j.finished,
                'result':result,'error':j.error,'cancelRequested':j.cancel.is_set(),
            })
        return out

    def persist(self)->Path:
        p=layout()['state']/'jobs.json'; p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps({'schema':'forgepy.jobs.v2','version':JOBS_VERSION,'jobs':self.snapshot()},indent=2,default=str)+'\n',encoding='utf-8')
        return p

    def shutdown(self)->None:self._pool.shutdown(wait=False,cancel_futures=True)
