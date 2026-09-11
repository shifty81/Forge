#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess, tempfile, uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from VaultPaths import vault_root

UNIFIED_DIFF_VERSION='FORGEPY-UNIFIED-DIFF-1.0'
_DIFF_RE=re.compile(r'^diff --git a/(.+?) b/(.+?)$',re.M)

def utc_now()->str:return datetime.now(timezone.utc).isoformat()

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def _safe_rel(raw:str)->str:
    value=raw.strip().strip('"').replace('\\','/')
    p=PurePosixPath(value)
    if not value or p.is_absolute() or re.match(r'^[A-Za-z]:',value) or any(x in {'','.','..'} for x in p.parts):
        raise RuntimeError(f'unsafe unified-diff path: {raw!r}')
    return '/'.join(p.parts)

def is_unified_diff(path:Path)->bool:
    path=path.expanduser()
    if not path.is_file() or path.suffix.casefold()!='.patch':return False
    try:
        head=path.read_bytes()[:262144].decode('utf-8-sig',errors='replace')
    except OSError:return False
    return bool(re.search(r'(?m)^diff --git a/.+ b/.+$',head) and re.search(r'(?m)^@@ ',head))

def changed_paths(path:Path)->list[str]:
    text=path.read_text(encoding='utf-8-sig',errors='strict')
    out=[]
    for old,new in _DIFF_RE.findall(text):
        for raw in (old,new):
            rel=_safe_rel(raw)
            if rel not in out:out.append(rel)
    if not out:raise RuntimeError('unified diff contains no git file headers')
    return out

def synthetic_manifest(path:Path,project:str='unassigned')->dict[str,Any]:
    patch_id=re.sub(r'[^A-Za-z0-9._-]+','-',path.stem).strip('-._')[:128] or f'diff-{sha256_file(path)[:12]}'
    created=datetime.fromtimestamp(path.stat().st_mtime,tz=timezone.utc).isoformat()
    return {
        'schema':'forge.patch.unified-diff.v1','engine':'forge-git-diff','patchId':patch_id,
        'project':project or 'unassigned','title':path.stem,'createdUtc':created,
        'transportFormat':'unified-diff','files':[{'path':x} for x in changed_paths(path)],
        'preconditions':{'gitApplyCheck':True},
    }

def _git(root:Path,*args:str,timeout:float=30)->subprocess.CompletedProcess[str]:
    flags=int(getattr(subprocess,'CREATE_NO_WINDOW',0)) if os.name=='nt' else 0
    return subprocess.run(['git','-C',str(root),*args],text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False,creationflags=flags)

def validate(path:Path,root:Path)->dict[str,Any]:
    path=path.expanduser().resolve(); root=root.expanduser().resolve()
    if not is_unified_diff(path):raise RuntimeError('not a Git unified-diff .patch transport')
    top=_git(root,'rev-parse','--show-toplevel',timeout=8)
    if top.returncode!=0:raise RuntimeError('unified-diff patches require a Git working tree')
    check=_git(root,'apply','--check','--whitespace=nowarn',str(path),timeout=30)
    if check.returncode!=0:
        detail=(check.stderr or check.stdout or 'git apply --check failed').strip()
        raise RuntimeError('unified diff does not apply cleanly to the active project: '+detail)
    return {'ok':True,'format':'unified-diff','paths':changed_paths(path),'sha256':sha256_file(path),'gitTopLevel':top.stdout.strip()}

def apply(path:Path,root:Path)->dict[str,Any]:
    path=path.expanduser().resolve(); root=root.expanduser().resolve(); checked=validate(path,root)
    manifest=synthetic_manifest(path,root.name); patch_id=manifest['patchId']
    project=re.sub(r'[^A-Za-z0-9._-]+','-',root.name).strip('-') or 'project'
    txid=f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    recovery=vault_root()/'recovery'/project/patch_id/txid
    preimage=recovery/'preimage'; preimage.mkdir(parents=True,exist_ok=True)
    states=[]
    try:
        for rel in checked['paths']:
            target=(root/rel).resolve()
            try:target.relative_to(root)
            except ValueError:raise RuntimeError(f'patch target escapes project root: {rel}')
            existed=target.is_file()
            if existed:
                backup=preimage/rel; backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,backup)
            states.append({'path':rel,'existed':existed})
        cp=_git(root,'apply','--whitespace=nowarn',str(path),timeout=120)
        if cp.returncode!=0:
            raise RuntimeError((cp.stderr or cp.stdout or 'git apply failed').strip())
        reverse=_git(root,'apply','--reverse','--check','--whitespace=nowarn',str(path),timeout=30)
        if reverse.returncode!=0:
            raise RuntimeError('post-apply reversibility check failed: '+(reverse.stderr or reverse.stdout).strip())
        receipt_dir=root/'artifacts'/'patches'/'receipts'; receipt_dir.mkdir(parents=True,exist_ok=True)
        receipt={'schema':'forge.patch.receipt.v1','engineVersion':UNIFIED_DIFF_VERSION,'patchId':patch_id,
                 'title':manifest['title'],'project':project,'status':'applied','transactionId':txid,
                 'transport':str(path),'transportFormat':'unified-diff','transportSha256':checked['sha256'],
                 'appliedUtc':utc_now(),'files':states,'recovery':str(recovery)}
        rp=receipt_dir/f'{patch_id}.json'; tmp=rp.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8'); os.replace(tmp,rp)
        (recovery/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        return receipt
    except Exception:
        # Restore captured preimages; remove paths that did not exist before.
        for row in reversed(states):
            target=root/row['path']; backup=preimage/row['path']
            try:
                if row['existed'] and backup.is_file():
                    target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(backup,target)
                elif not row['existed'] and target.is_file():target.unlink()
            except Exception:pass
        raise
