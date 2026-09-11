#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
COMPLIANCE_VERSION='FORGEPY-ADAPTER-COMPLIANCE-1.0'
RECOMMENDED={'gate.full','build','run'}
def audit(adapter:dict[str,Any])->dict[str,Any]:
    caps=set((adapter.get('capabilities') or {}).keys()) if isinstance(adapter.get('capabilities'),dict) else set(adapter.get('capabilities') or [])
    missing=sorted(RECOMMENDED-caps)
    return {'schema':'forgepy.adapter-compliance.v1','version':COMPLIANCE_VERSION,'ok':not missing,'missingRecommended':missing,'capabilityCount':len(caps),'projectId':adapter.get('projectId')}
