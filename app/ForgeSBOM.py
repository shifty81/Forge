#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
from ForgeDependencyInventory import scan
SBOM_VERSION='FORGEPY-SBOM-1.0'
def generate(root)->dict[str,Any]:
    inv=scan(root); comps=[]
    for i,row in enumerate(inv['rows']):comps.append({'type':'library','bom-ref':f'forgepy-{i}','name':row['declaration'],'group':row['ecosystem'],'properties':[{'name':'source','value':row['source']}]})
    return {'bomFormat':'CycloneDX','specVersion':'1.5','version':1,'metadata':{'tools':[{'vendor':'ForgePY','name':'Dependency Inventory','version':SBOM_VERSION}]},'components':comps}
