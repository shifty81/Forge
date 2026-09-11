#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path
from typing import Any
from ForgeCommandBus import CommandBus
from ForgePluginRegistry import PluginSpec, load as load_registry, validate
from ForgeVaultBootstrap import layout

PLUGIN_RUNTIME_VERSION="FORGEPY-PLUGIN-RUNTIME-1.0"

def plugin_root()->Path:
    p=layout()['components']/'plugins'; p.mkdir(parents=True,exist_ok=True); return p

def discover_manifests()->list[dict[str,Any]]:
    rows=[]
    for p in plugin_root().rglob('plugin.json'):
        try:
            data=json.loads(p.read_text(encoding='utf-8-sig')); data['_path']=str(p); rows.append(data)
        except Exception: continue
    return rows

def effective_permissions(spec:PluginSpec)->set[str]:
    return set(spec.permissions)

def load_enabled(bus:CommandBus)->dict[str,Any]:
    loaded=[]; blocked=[]
    for spec in load_registry():
        errs=validate(spec)
        if errs: blocked.append({'plugin':spec.plugin_id,'reason':'; '.join(errs)}); continue
        if not spec.enabled: continue
        entry=Path(spec.entrypoint)
        if not entry.is_absolute(): entry=plugin_root()/entry
        if not entry.is_file():
            blocked.append({'plugin':spec.plugin_id,'reason':'entrypoint missing'}); continue
        try:
            module_name='forgepy_plugin_'+''.join(c if c.isalnum() else '_' for c in spec.plugin_id)
            module_spec=importlib.util.spec_from_file_location(module_name,entry)
            if module_spec is None or module_spec.loader is None: raise RuntimeError('loader unavailable')
            module=importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
            register=getattr(module,'register',None)
            if not callable(register): raise RuntimeError('plugin must expose register(bus, permissions)')
            register(bus,frozenset(effective_permissions(spec)))
            loaded.append(spec.plugin_id)
        except Exception as exc:
            blocked.append({'plugin':spec.plugin_id,'reason':str(exc)})
    return {'version':PLUGIN_RUNTIME_VERSION,'loaded':loaded,'blocked':blocked}
