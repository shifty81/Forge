#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

CHECKPOINT_VERSION = "FORGEPY-PATCH-CHECKPOINT-1.0-F570"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_rel(raw: str) -> str:
    value = str(raw or "").replace("\\", "/").strip("/")
    parts = Path(value).parts
    if not value or Path(value).is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe checkpoint path: {raw!r}")
    return "/".join(parts)


def _target(root: Path, rel: str) -> Path:
    root = root.resolve()
    path = (root / Path(rel)).resolve()
    path.relative_to(root)
    return path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _checkpoint_root(project_root: Path, project_id: str) -> Path:
    try:
        from VaultPaths import vault_root
        base = Path(vault_root())
    except Exception:
        try:
            from ForgePYPaths import data_root
            base = Path(data_root())
        except Exception:
            base = project_root / "artifacts"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_project = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in project_id).strip("-") or project_root.name
    return base / "recovery" / "batch-updates" / safe_project / f"{stamp}-{uuid.uuid4().hex[:8]}"


def create(root: Path, transports: Iterable[Path], *, project_id: str = "") -> dict[str, Any]:
    """Create one efficient touched-file checkpoint for a universal patch batch.

    The checkpoint is created before the first project-source write. Each target path is
    backed up at most once even if multiple queued patches touch it. Paths that did not
    exist are recorded so rollback can remove files created by an earlier patch.
    """
    from ForgePYPatchEngine import validate_transport

    root = root.expanduser().resolve()
    sources = [Path(path).expanduser().resolve() for path in transports]
    if not sources:
        raise ValueError("checkpoint requires at least one patch transport")
    checkpoint = _checkpoint_root(root, project_id or root.name)
    preimage = checkpoint / "preimage"
    preimage.mkdir(parents=True, exist_ok=False)

    touched: dict[str, dict[str, Any]] = {}
    validated: list[dict[str, Any]] = []
    for source in sources:
        # Validate transport structure/payload hashes without enforcing every preimage
        # against the initial tree. Later patches in one approved batch may legitimately
        # depend on files produced by an earlier patch; apply_transport validates each
        # patch against the then-current source immediately before mutation.
        checked = validate_transport(source)
        rows = list(checked.get("files") or [])
        validated.append({
            "path": str(source),
            "sha256": str(checked.get("sha256") or ""),
            "fileCount": len(rows),
        })
        for row in rows:
            rel = _safe_rel(str(row.get("path") or row.get("target") or ""))
            if rel in touched:
                continue
            target = _target(root, rel)
            if target.exists() and not target.is_file():
                raise RuntimeError(f"checkpoint target is not a regular file: {rel}")
            record: dict[str, Any] = {"path": rel, "existed": target.is_file(), "sha256": "", "bytes": 0}
            if target.is_file():
                backup = preimage / Path(rel)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                record["sha256"] = _sha256(backup)
                record["bytes"] = backup.stat().st_size
            touched[rel] = record

    manifest = {
        "schema": "forgepy.patch-batch-checkpoint.v1",
        "version": CHECKPOINT_VERSION,
        "state": "READY",
        "createdUtc": _utc(),
        "projectRoot": str(root),
        "projectId": project_id or root.name,
        "transports": validated,
        "files": [touched[key] for key in sorted(touched, key=str.casefold)],
    }
    manifest_path = checkpoint / "checkpoint.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(checkpoint), "manifest": str(manifest_path), "files": len(touched), "state": "READY"}


def _load(checkpoint: Path) -> tuple[Path, Path, dict[str, Any]]:
    checkpoint = checkpoint.expanduser().resolve()
    manifest_path = checkpoint / "checkpoint.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    root = Path(str(data.get("projectRoot") or "")).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError(f"checkpoint project root is unavailable: {root}")
    return checkpoint, root, data


def mark(checkpoint: Path, state: str, *, detail: str = "") -> dict[str, Any]:
    checkpoint, _root, data = _load(checkpoint)
    data["state"] = str(state)
    data["updatedUtc"] = _utc()
    if detail:
        data["detail"] = str(detail)
    path = checkpoint / "checkpoint.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return data


def restore(checkpoint: Path) -> dict[str, Any]:
    checkpoint, root, data = _load(checkpoint)
    preimage = checkpoint / "preimage"
    restored = 0
    removed = 0
    errors: list[str] = []
    rows = list(data.get("files") or [])
    for row in reversed(rows):
        rel = _safe_rel(str(row.get("path") or ""))
        target = _target(root, rel)
        try:
            if bool(row.get("existed")):
                backup = preimage / Path(rel)
                if not backup.is_file():
                    raise RuntimeError("checkpoint preimage missing")
                expected = str(row.get("sha256") or "")
                if expected and _sha256(backup) != expected:
                    raise RuntimeError("checkpoint preimage hash mismatch")
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(prefix=target.name + ".forge-restore-", dir=str(target.parent))
                os.close(fd)
                try:
                    shutil.copy2(backup, temp_name)
                    os.replace(temp_name, target)
                finally:
                    try:
                        os.unlink(temp_name)
                    except FileNotFoundError:
                        pass
                restored += 1
            else:
                if target.is_file():
                    target.unlink()
                    removed += 1
                # Remove only empty parents created by the patch, stopping at project root.
                parent = target.parent
                while parent != root:
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent
        except Exception as exc:
            errors.append(f"{rel}: {exc}")

    state = "ROLLED_BACK" if not errors else "ROLLBACK_FAILED"
    mark(checkpoint, state, detail="; ".join(errors[:20]))
    return {"ok": not errors, "restored": restored, "removed": removed, "errors": errors, "path": str(checkpoint)}
