#!/usr/bin/env python3
from __future__ import annotations
import json,threading
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from ForgeVaultBootstrap import layout
PROVENANCE_VERSION='FORGEPY-PROVENANCE-1.0';_LOCK=threading.Lock()
def path()->Path:return layout()['state']/'provenance-ledger.jsonl'
def append(kind:str,subject:str,**data:Any)->Path:
    p=path(); p.parent.mkdir(parents=True,exist_ok=True); row={'schema':'forgepy.provenance.v1','version':PROVENANCE_VERSION,'utc':datetime.now(timezone.utc).isoformat(),'kind':kind,'subject':subject,**data}
    with _LOCK:
        with p.open('a',encoding='utf-8') as fh:fh.write(json.dumps(row,sort_keys=True)+'\n')
    return p
