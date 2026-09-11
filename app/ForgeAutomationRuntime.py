#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
from ForgeAutomationProfiles import AutomationProfile

AUTOMATION_RUNTIME_VERSION="FORGEPY-AUTOMATION-RUNTIME-1.0"

def evaluate(profile:AutomationProfile, context:dict[str,Any])->dict[str,Any]:
    if not profile.enabled:
        return {'eligible':False,'reason':'profile disabled'}
    if profile.trigger != 'manual' and not context.get('automationEnabled',False):
        return {'eligible':False,'reason':'scheduled/event automation globally disabled'}
    condition=(profile.condition or '').strip()
    if condition:
        key,sep,value=condition.partition('=')
        if not sep or str(context.get(key.strip(),'')).casefold()!=value.strip().casefold():
            return {'eligible':False,'reason':'condition not satisfied'}
    return {'eligible':True,'requiresConfirmation':bool(profile.requires_confirmation),'command':profile.command}
