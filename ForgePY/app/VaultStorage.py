#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from VaultSettings import load_settings, save_settings

STORAGE_VERSION = "VAULT-STORAGE-0.5"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _copy_tree(source: Path, target: Path, progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, int]:
    files = copied = reused = 0
    if not source.exists():
        return {"files": 0, "copied": 0, "reused": 0}
    for base, dirs, names in os.walk(source):
        base_path = Path(base)
        rel_dir = base_path.relative_to(source)
        dest_dir = target / rel_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            src = base_path / name
            dst = dest_dir / name
            files += 1
            if dst.is_file() and src.stat().st_size == dst.stat().st_size and _sha(src) == _sha(dst):
                reused += 1
            else:
                temp = dst.with_name(dst.name + ".vault-copying")
                shutil.copy2(src, temp)
                if _sha(src) != _sha(temp):
                    temp.unlink(missing_ok=True)
                    raise RuntimeError(f"Vault home migration hash mismatch: {src}")
                os.replace(temp, dst)
                copied += 1
            if progress and files % 100 == 0:
                progress({"files": files, "copied": copied, "reused": reused})
    return {"files": files, "copied": copied, "reused": reused}


def migrate_home(source: Path, target: Path, *, keep_source: bool = True, progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    source = source.expanduser().resolve()
    target = target.expanduser().resolve()
    if source == target:
        target.mkdir(parents=True, exist_ok=True)
        return {"status": "already-there", "source": str(source), "target": str(target), "files": 0, "copied": 0, "reused": 0}
    # Never recurse a Vault home into itself or overwrite a parent with a child tree.
    try:
        target.relative_to(source)
        raise RuntimeError(f"Vault home target cannot be inside the current Vault home: {target}")
    except ValueError:
        pass
    try:
        source.relative_to(target)
        raise RuntimeError(f"Vault home target cannot be a parent of the current Vault home: {target}")
    except ValueError:
        pass
    target.mkdir(parents=True, exist_ok=True)
    stats = _copy_tree(source, target, progress)
    data = load_settings()
    old_home = Path(str(data.get("vaultHome") or source)).expanduser()
    data["vaultHome"] = str(target)
    forgejo = dict(data.get("forgejo") or {})
    if not forgejo.get("workPath") or Path(str(forgejo.get("workPath"))) == old_home / "Forgejo":
        forgejo["workPath"] = str(target / "Forgejo")
    if not forgejo.get("config") or Path(str(forgejo.get("config"))) == old_home / "Forgejo" / "custom" / "conf" / "app.ini":
        forgejo["config"] = str(target / "Forgejo" / "custom" / "conf" / "app.ini")
    data["forgejo"] = forgejo
    settings_path = save_settings(data)
    receipt = {
        "schema": "vault.storage.migration.v1",
        "version": STORAGE_VERSION,
        "timestampUtc": utc_now(),
        "status": "migrated",
        "source": str(source),
        "target": str(target),
        "keepSource": bool(keep_source),
        **stats,
        "settings": str(settings_path),
    }
    evidence = target / "recovery" / "storage-migrations"
    evidence.mkdir(parents=True, exist_ok=True)
    receipt_path = evidence / (datetime.now().strftime("%Y%m%d-%H%M%S") + ".json")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt"] = str(receipt_path)
    # Fail-safe default: source data is retained. Cleanup becomes an explicit later operation.
    return receipt



def _tree_fingerprint(root: Path) -> dict[str, tuple[int, str]]:
    """Return a deterministic regular-file fingerprint for verified project migration."""
    rows: dict[str, tuple[int, str]] = {}
    for base, dirs, names in os.walk(root, followlinks=False):
        base_path = Path(base)
        # Avoid traversing directory symlinks/junction-like links. Their target contents are
        # not copied as independent project data by the portable migration contract.
        dirs[:] = [name for name in dirs if not (base_path / name).is_symlink()]
        for name in names:
            path = base_path / name
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            rows[rel] = (path.stat().st_size, _sha(path))
    return rows


def migrate_project(
    source: Path,
    projects_root: Path,
    *,
    target_name: str = "",
    keep_source: bool = True,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Create a hash-verified portable project copy under the configured Projects Root.

    The source is intentionally retained by default.  Vault first copies to a staging folder on
    the destination volume, verifies every regular file, then atomically renames the staging
    directory into place.  Registry rebinding is handled by the caller only after this succeeds.
    """
    source = source.expanduser().resolve()
    projects_root = projects_root.expanduser().resolve()
    if not source.is_dir():
        raise RuntimeError(f"Project source does not exist: {source}")
    projects_root.mkdir(parents=True, exist_ok=True)
    name = (target_name or source.name).strip()
    if not name or name in {".", ".."} or any(ch in name for ch in '<>:"/\\|?*'):
        raise RuntimeError(f"Invalid portable project folder name: {name!r}")
    target = (projects_root / name).resolve()
    if source == target:
        return {
            "status": "already-there", "source": str(source), "target": str(target),
            "files": 0, "copied": 0, "reused": 0, "keepSource": True,
        }
    try:
        target.relative_to(source)
        raise RuntimeError(f"Portable project target cannot be inside the source project: {target}")
    except ValueError:
        pass
    try:
        source.relative_to(target)
        raise RuntimeError(f"Portable project target cannot be a parent of the source project: {target}")
    except ValueError:
        pass
    if target.exists():
        raise RuntimeError(f"Portable project target already exists: {target}")

    staging_root = projects_root / ".vault-migration-staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    stage = staging_root / f"{name}-{uuid.uuid4().hex[:10]}"
    stage.mkdir(parents=True, exist_ok=False)
    started = utc_now()
    try:
        stats = _copy_tree(source, stage, progress)
        if progress:
            progress({**stats, "phase": "verifying"})
        source_fp = _tree_fingerprint(source)
        target_fp = _tree_fingerprint(stage)
        if source_fp != target_fp:
            missing = sorted(set(source_fp) - set(target_fp))[:5]
            extra = sorted(set(target_fp) - set(source_fp))[:5]
            changed = sorted(k for k in set(source_fp) & set(target_fp) if source_fp[k] != target_fp[k])[:5]
            raise RuntimeError(
                "Portable project verification failed; source changed during copy or destination differs. "
                f"missing={missing}, extra={extra}, changed={changed}"
            )
        os.replace(stage, target)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    data = load_settings()
    vault_home = Path(str(data.get("vaultHome") or projects_root.parent / "Vault")).expanduser()
    evidence = vault_home / "recovery" / "project-migrations"
    evidence.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "vault.project-migration.v1",
        "version": STORAGE_VERSION,
        "startedUtc": started,
        "completedUtc": utc_now(),
        "status": "migrated",
        "source": str(source),
        "target": str(target),
        "projectsRoot": str(projects_root),
        "keepSource": bool(keep_source),
        "files": len(source_fp),
        "verifiedFiles": len(target_fp),
        **stats,
    }
    receipt_path = evidence / (datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{name}.json")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt"] = str(receipt_path)
    # Source deletion is deliberately not implemented in this pass.  The old working tree is
    # rollback evidence until the operator explicitly performs a later cleanup/reclaim action.
    return receipt
