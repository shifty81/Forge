#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
VAULT_MODEL_VERSION='FORGEPY-VAULT-MODEL-1.0'
GROUPS=('Projects','Project Families','Source','Assets','Archives','Patches','Builds','Documentation','Generated','Cache','Duplicates','Unclassified')
_SOURCE_EXT={'.py','.rs','.cpp','.cc','.c','.h','.hpp','.cs','.java','.js','.ts','.gd','.lua','.ps1','.cmd','.bat','.sh','.toml','.cmake'}
_ASSET_EXT={'.png','.jpg','.jpeg','.webp','.gif','.svg','.blend','.fbx','.obj','.glb','.gltf','.wav','.ogg','.mp3','.aseprite'}
_DOC_EXT={'.md','.txt','.pdf','.doc','.docx','.rtf'}
_ARCHIVE_EXT={'.zip','.7z','.rar','.tar','.gz','.bz2','.xz'}
def classify(path:Path|str, *, existing:str='')->str:
    if existing and existing.upper() not in {'UNKNOWN','UNCLASSIFIED'}: return existing
    p=Path(path); n=p.name.casefold(); ext=p.suffix.casefold(); parts={x.casefold() for x in p.parts}
    if ext=='.patch' or 'patch' in n:return 'Patches'
    if ext in _SOURCE_EXT:return 'Source'
    if ext in _ASSET_EXT:return 'Assets'
    if ext in _DOC_EXT:return 'Documentation'
    if ext in _ARCHIVE_EXT:return 'Archives'
    if any(x in parts for x in {'target','build','dist','out','bin','obj'}):return 'Builds'
    if any(x in parts for x in {'__pycache__','.cache','cache','node_modules'}):return 'Cache'
    if any(x in parts for x in {'generated','gen'}):return 'Generated'
    return 'Unclassified'
def summarize(rows:list[dict[str,Any]])->dict[str,int]:
    counts={k:0 for k in GROUPS}
    for row in rows: counts[classify(row.get('path') or row.get('name') or '',existing=str(row.get('classification') or ''))]=counts.get(classify(row.get('path') or '',existing=str(row.get('classification') or '')),0)+1
    return counts
