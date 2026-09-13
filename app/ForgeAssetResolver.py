#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ForgePYPaths import artifact_central_root, vault_root
from VaultArtifacts import safe_project_id

ASSET_RESOLVER_VERSION = "FORGEPY-ASSET-RESOLVER-1.0-F797"
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".blend", ".fbx", ".obj", ".glb", ".gltf", ".wav", ".ogg", ".mp3", ".aseprite", ".ktx", ".ktx2"}
_REQUIREMENT_FILES = (
    "forge.assets.json",
    ".forge/assets.json",
    "config/forge.assets.json",
    "assets/forge.assets.json",
    "asset_requirements.json",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _project_id(root: Path) -> str:
    try:
        from PCCProjectDiscovery import discover_project_contract_data
        project = (discover_project_contract_data(root).get("project") or {})
        return safe_project_id(str(project.get("id") or root.name))
    except Exception:
        return safe_project_id(root.name)


def _normalize_requirement(raw: dict[str, Any], *, source: str) -> dict[str, Any] | None:
    name = str(raw.get("name") or raw.get("sourceName") or raw.get("fileName") or "").strip()
    digest = str(raw.get("sha256") or raw.get("sourceSha256") or "").strip().casefold()
    asset_id = str(raw.get("id") or raw.get("assetId") or Path(name).stem or "asset").strip()
    destination = str(raw.get("destination") or raw.get("materializeTo") or raw.get("projectPath") or name).strip()
    if not name and not digest:
        return None
    return {
        "id": asset_id,
        "name": name,
        "sha256": digest,
        "destination": destination,
        "required": bool(raw.get("required", True)),
        "license": str(raw.get("license") or "").strip(),
        "provenance": str(raw.get("provenance") or raw.get("source") or "").strip(),
        "source": source,
    }


def requirements(root: Path) -> list[dict[str, Any]]:
    root = root.expanduser().resolve()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for rel in _REQUIREMENT_FILES:
        path = root / rel
        if not path.is_file():
            continue
        data = _read_json(path)
        raw_rows = data.get("assets") if isinstance(data.get("assets"), list) else data.get("requirements")
        for raw in raw_rows or []:
            if not isinstance(raw, dict):
                continue
            row = _normalize_requirement(raw, source=rel)
            if row is None:
                continue
            key = (row["name"].casefold(), row["sha256"])
            if key not in seen:
                seen.add(key); rows.append(row)
    try:
        from PCCProjectDiscovery import discover_project_contract_data
        contract = discover_project_contract_data(root)
        candidates = []
        if isinstance(contract.get("assetRequirements"), list):
            candidates.extend(contract.get("assetRequirements") or [])
        deps = contract.get("dependencies") if isinstance(contract.get("dependencies"), dict) else {}
        if isinstance(deps.get("assets"), list):
            candidates.extend(deps.get("assets") or [])
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            row = _normalize_requirement(raw, source="project.control.json")
            if row is None:
                continue
            key = (row["name"].casefold(), row["sha256"])
            if key not in seen:
                seen.add(key); rows.append(row)
    except Exception:
        pass
    return rows




def _project_destination(root: Path, raw: str) -> Path:
    value = str(raw or "").replace("\\", "/").strip()
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise RuntimeError(f"unsafe asset destination: {raw!r}")
    parts = [part for part in value.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise RuntimeError(f"unsafe asset destination: {raw!r}")
    target = (root / Path(*parts)).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"asset destination escapes project root: {raw!r}") from exc
    return target

def _candidate_file(path: Path, req: dict[str, Any], authority: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    if req.get("name") and path.name.casefold() != str(req["name"]).casefold():
        return None
    digest = ""
    expected = str(req.get("sha256") or "").casefold()
    if expected:
        try: digest = _sha256(path)
        except OSError: return None
        if digest != expected:
            return None
    return {"authority": authority, "path": str(path), "member": "", "sha256": digest or expected, "exactHash": bool(expected)}


def _artifact_candidates(req: dict[str, Any], limit: int = 300) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    name = str(req.get("name") or "")
    try:
        from ForgeArtifactIndex import search
        for row in (search(query=name, limit=limit).get("rows") or []):
            hit = _candidate_file(Path(str(row.get("path") or "")), req, "artifact-central")
            if hit: out.append(hit)
    except Exception:
        pass
    try:
        from ForgeVaultSearch import search
        for row in (search(name, limit=limit).get("rows") or []):
            hit = _candidate_file(Path(str(row.get("path") or "")), req, "vault-drive-catalog")
            if hit: out.append(hit)
    except Exception:
        pass
    return out


def _backup_roots() -> list[Path]:
    roots = [vault_root() / "backups", artifact_central_root() / "backups", artifact_central_root() / "projects"]
    return [p for p in roots if p.is_dir()]


def _backup_candidates(req: dict[str, Any], max_archives: int = 120) -> list[dict[str, Any]]:
    name = str(req.get("name") or "").casefold()
    expected = str(req.get("sha256") or "").casefold()
    out: list[dict[str, Any]] = []
    archives: list[Path] = []
    for root in _backup_roots():
        try: archives.extend(root.rglob("*.zip"))
        except OSError: pass
        if len(archives) >= max_archives * 2: break
    try: archives = sorted(set(archives), key=lambda p: p.stat().st_mtime, reverse=True)[:max_archives]
    except OSError: archives = archives[:max_archives]
    for archive in archives:
        try:
            with zipfile.ZipFile(archive, "r") as zf:
                names = {n.replace("\\", "/"): n for n in zf.namelist() if not n.endswith("/")}
                manifest_name = next((actual for norm, actual in names.items() if norm.casefold() == "forgepy_backup_manifest.json"), "")
                if not manifest_name:
                    continue
                manifest = json.loads(zf.read(manifest_name).decode("utf-8-sig"))
                for row in manifest.get("files", []) or []:
                    rel = str(row.get("path") or "")
                    if name and Path(rel).name.casefold() != name:
                        continue
                    digest = str(row.get("sha256") or "").casefold()
                    if expected and digest != expected:
                        continue
                    if rel not in names:
                        continue
                    out.append({"authority": "backup-catalog", "path": str(archive), "member": rel, "sha256": digest, "exactHash": bool(expected)})
        except Exception:
            continue
    return out


def find_candidates(req: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _artifact_candidates(req) + _backup_candidates(req)
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        unique[(str(row.get("path")), str(row.get("member")))] = row
    return list(unique.values())


def _materialize_candidate(candidate: dict[str, Any], destination: Path, expected: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".forge-", dir=str(destination.parent))
    os.close(fd)
    temp = Path(temp_name)
    try:
        member = str(candidate.get("member") or "")
        if member:
            with zipfile.ZipFile(Path(str(candidate["path"])), "r") as zf:
                temp.write_bytes(zf.read(member))
        else:
            shutil.copy2(Path(str(candidate["path"])), temp)
        if expected and _sha256(temp) != expected:
            raise RuntimeError("hydrated asset hash mismatch")
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


def status(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    rows = []
    for req in requirements(root):
        try:
            dest = _project_destination(root, str(req.get("destination") or req.get("name") or ""))
        except Exception as exc:
            rows.append({**req, "projectPath": "", "ready": False, "reason": str(exc), "candidateCount": 0, "candidates": []})
            continue
        ready = False
        reason = "missing"
        if dest.is_file():
            expected = str(req.get("sha256") or "")
            ready = not expected or _sha256(dest) == expected
            reason = "ready" if ready else "project copy hash mismatch"
        candidates = [] if ready else find_candidates(req)
        rows.append({**req, "projectPath": str(dest), "ready": ready, "reason": reason, "candidateCount": len(candidates), "candidates": candidates[:12]})
    required = [r for r in rows if r.get("required")]
    return {
        "schema": "forgepy.asset-resolution.v1", "version": ASSET_RESOLVER_VERSION,
        "root": str(root), "requirements": rows, "required": len(required),
        "ready": sum(1 for r in required if r.get("ready")),
        "missing": sum(1 for r in required if not r.get("ready")),
    }


def _write_report(root: Path, payload: dict[str, Any], name: str) -> str:
    project = _project_id(root)
    folder = artifact_central_root() / "projects" / project / "reports" / "asset-resolution" / "current"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return str(path)


def hydrate(root: Path, *, apply: bool = True) -> dict[str, Any]:
    root = root.expanduser().resolve()
    before = status(root)
    actions: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in before.get("requirements", []):
        if row.get("ready") or not row.get("required"):
            continue
        candidates = list(row.get("candidates") or [])
        expected = str(row.get("sha256") or "")
        # Automatic hydration requires a hash-bound requirement and exactly one matching source.
        if not expected:
            errors.append(f"{row.get('id')}: no authoritative SHA-256; review required")
            continue
        if len(candidates) != 1:
            errors.append(f"{row.get('id')}: expected one exact Vault source, found {len(candidates)}")
            continue
        dest = Path(str(row.get("projectPath") or ""))
        if apply:
            try:
                _materialize_candidate(candidates[0], dest, expected)
                actions.append({"id": row.get("id"), "destination": str(dest), "source": candidates[0], "status": "hydrated"})
            except Exception as exc:
                errors.append(f"{row.get('id')}: {exc}")
        else:
            actions.append({"id": row.get("id"), "destination": str(dest), "source": candidates[0], "status": "would-hydrate"})
    after = status(root) if apply and actions else before
    payload = {**after, "actions": actions, "errors": errors, "apply": bool(apply), "timestampUtc": datetime.now(timezone.utc).isoformat()}
    payload["report"] = _write_report(root, payload, "latest.json")
    return payload


def diagnose_recent_logs(root: Path, *, max_logs: int = 8) -> dict[str, Any]:
    """Find asset names mentioned by recent project logs and correlate them with Vault.

    This is advisory only. It never copies an inferred asset because the project has not
    declared a destination/hash contract. It is intended to turn failures such as a missing
    GLB/texture into actionable Vault/backup candidates instead of a dead-end error.
    """
    root = root.expanduser().resolve()
    logs: list[Path] = []
    for folder in (root / "logs" / "sessions", root / "artifacts" / "logs" / "sessions"):
        if folder.is_dir():
            try: logs.extend(p for p in folder.iterdir() if p.is_file())
            except OSError: pass
    try: logs = sorted(logs, key=lambda p: p.stat().st_mtime, reverse=True)[:max_logs]
    except OSError: logs = logs[:max_logs]
    mentions: dict[str, dict[str, Any]] = {}
    asset_re = re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z0-9][A-Za-z0-9_. ()+\-]{0,180}\.(?:glb|gltf|fbx|obj|png|jpg|jpeg|webp|blend|wav|ogg|aseprite|ktx2?))", re.I)
    hash_re = re.compile(r"\b[0-9a-fA-F]{64}\b")
    for log in logs:
        try: text = log.read_text(encoding="utf-8", errors="replace")[-500000:]
        except OSError: continue
        for match in asset_re.finditer(text):
            name = Path(match.group(1).strip().strip('"\'')).name
            if Path(name).suffix.casefold() not in ASSET_EXTENSIONS:
                continue
            window = text[max(0, match.start()-600): min(len(text), match.end()+600)]
            hashes = hash_re.findall(window)
            row = mentions.setdefault(name.casefold(), {"name": name, "hashHints": set(), "logs": set()})
            row["hashHints"].update(h.casefold() for h in hashes)
            row["logs"].add(str(log))
    results = []
    for row in mentions.values():
        hash_hints = sorted(row["hashHints"])
        req = {"name": row["name"], "sha256": hash_hints[0] if len(hash_hints) == 1 else ""}
        candidates = find_candidates(req)
        results.append({"name": row["name"], "hashHints": hash_hints, "logs": sorted(row["logs"]), "candidateCount": len(candidates), "candidates": candidates[:12]})
    results.sort(key=lambda r: (-int(r["candidateCount"]), str(r["name"]).casefold()))
    payload = {"schema": "forgepy.asset-diagnostics.v1", "version": ASSET_RESOLVER_VERSION, "root": str(root), "mentions": results}
    payload["report"] = _write_report(root, payload, "diagnostics-latest.json")
    return payload


__all__ = ["requirements", "status", "hydrate", "find_candidates", "diagnose_recent_logs", "ASSET_RESOLVER_VERSION"]
