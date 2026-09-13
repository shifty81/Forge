#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

BRIDGE_VERSION = "FORGE-NATIVE-UPDATE-BRIDGE-1.0-F807"
MANIFEST_NAME = "FORGE_NATIVE_UPDATE_MANIFEST.json"
MANIFEST_SCHEMA = "forge.native.application-update.v1"
MAX_FILES = 50_000
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value: str) -> str:
    raw = value.replace("\\", "/").strip()
    pure = PurePosixPath(raw)
    if not raw or raw.startswith("/") or pure.is_absolute():
        raise RuntimeError(f"unsafe native update path: {value!r}")
    parts = pure.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise RuntimeError(f"unsafe native update path: {value!r}")
    if ":" in parts[0]:
        raise RuntimeError(f"unsafe native update path: {value!r}")
    return pure.as_posix()


def ensure_outside(child: Path, parent: Path) -> None:
    child = child.expanduser().resolve()
    parent = parent.expanduser().resolve()
    try:
        child.relative_to(parent)
    except ValueError:
        return
    raise RuntimeError(f"native update maintenance/staging must be outside the live application root: {child}")


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK


def _manifest_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if str(manifest.get("schema") or "") != MANIFEST_SCHEMA:
        raise RuntimeError("unsupported Forge Native application update schema")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Forge Native application update manifest has no files")
    if len(rows) > MAX_FILES:
        raise RuntimeError(f"Forge Native application update exceeds {MAX_FILES} files")

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("Forge Native application update contains an invalid file row")
        rel = safe_relative(str(row.get("path") or ""))
        key = rel.casefold()
        if key in seen:
            raise RuntimeError(f"duplicate Forge Native update manifest path: {rel}")
        seen.add(key)
        expected_hash = str(row.get("sha256") or "").casefold()
        if len(expected_hash) != 64 or any(ch not in "0123456789abcdef" for ch in expected_hash):
            raise RuntimeError(f"invalid SHA-256 in Forge Native update manifest: {rel}")
        try:
            size = int(row.get("bytes"))
        except Exception as exc:
            raise RuntimeError(f"invalid byte count in Forge Native update manifest: {rel}") from exc
        if size < 0 or size > MAX_FILE_BYTES:
            raise RuntimeError(f"Forge Native update file is outside size policy: {rel}")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise RuntimeError("Forge Native application update exceeds total size policy")
        normalized.append({"path": rel, "bytes": size, "sha256": expected_hash})
    return normalized


def inspect_bundle(bundle: Path, expected_entrypoint: str | None = None) -> dict[str, Any]:
    bundle = bundle.expanduser().resolve()
    if not bundle.is_file():
        raise FileNotFoundError(bundle)
    if bundle.suffix.casefold() != ".forgeupdate":
        raise RuntimeError("Forge Native packaged self-update requires a .forgeupdate transport")

    with zipfile.ZipFile(bundle, "r") as archive:
        infos = archive.infolist()
        names: dict[str, zipfile.ZipInfo] = {}
        total_uncompressed = 0
        for info in infos:
            normalized = info.filename.replace("\\", "/")
            key = normalized.casefold()
            if key in names:
                raise RuntimeError(f"duplicate archive entry in Forge Native update: {normalized}")
            names[key] = info
            if _is_symlink(info):
                raise RuntimeError(f"symbolic-link archive entries are not allowed: {normalized}")
            total_uncompressed += int(info.file_size)
            if total_uncompressed > MAX_TOTAL_BYTES:
                raise RuntimeError("Forge Native update archive exceeds total extraction size policy")

        manifest_info = names.get(MANIFEST_NAME.casefold())
        if manifest_info is None:
            raise RuntimeError(f"Forge Native application update is missing {MANIFEST_NAME}")
        try:
            manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("Forge Native application update manifest is invalid JSON") from exc
        if not isinstance(manifest, dict):
            raise RuntimeError("Forge Native application update manifest must be an object")

        rows = _manifest_rows(manifest)
        entrypoint = safe_relative(str(manifest.get("entrypoint") or ""))
        if expected_entrypoint and Path(entrypoint).name.casefold() != Path(expected_entrypoint).name.casefold():
            raise RuntimeError(
                f"Forge Native update entrypoint mismatch: manifest={entrypoint}, current={expected_entrypoint}"
            )
        if entrypoint.casefold() not in {row["path"].casefold() for row in rows}:
            raise RuntimeError("Forge Native application update entrypoint is not governed by the file manifest")

        expected_archive = {MANIFEST_NAME.casefold()}
        expected_archive.update(("image/" + row["path"]).casefold() for row in rows)
        actual_files = {
            info.filename.replace("\\", "/").casefold()
            for info in infos
            if not info.is_dir()
        }
        extras = sorted(actual_files - expected_archive)
        missing = sorted(expected_archive - actual_files)
        if extras:
            raise RuntimeError(f"unexpected files in Forge Native update bundle: {extras[:8]}")
        if missing:
            raise RuntimeError(f"missing files in Forge Native update bundle: {missing[:8]}")

        for row in rows:
            info = names[("image/" + row["path"]).casefold()]
            if int(info.file_size) != int(row["bytes"]):
                raise RuntimeError(f"Forge Native update size mismatch: {row['path']}")

    return {
        "manifest": manifest,
        "files": rows,
        "entrypoint": entrypoint,
        "transportSha256": sha256(bundle),
    }


def stage_bundle(
    bundle: Path,
    current_root: Path,
    maintenance_root: Path,
    mode: str,
    expected_entrypoint: str,
) -> dict[str, Any]:
    bundle = bundle.expanduser().resolve()
    current_root = current_root.expanduser().resolve()
    maintenance_root = maintenance_root.expanduser().resolve()
    if mode not in {"development", "portable", "installed"}:
        raise RuntimeError(f"unsupported Forge Native install mode: {mode}")
    ensure_outside(maintenance_root, current_root)
    inspected = inspect_bundle(bundle, expected_entrypoint)
    rows = inspected["files"]
    manifest = inspected["manifest"]

    staged_parent = maintenance_root / "Staged"
    staged_parent.mkdir(parents=True, exist_ok=True)
    staged = staged_parent / f"Forge-next-{uuid.uuid4().hex[:10]}"
    staged.mkdir(parents=True, exist_ok=False)
    ensure_outside(staged, current_root)

    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            stage_resolved = staged.resolve()
            for row in rows:
                rel = row["path"]
                target = (staged / rel).resolve()
                try:
                    target.relative_to(stage_resolved)
                except ValueError as exc:
                    raise RuntimeError(f"Forge Native update escapes staging root: {rel}") from exc
                target.parent.mkdir(parents=True, exist_ok=True)
                info = archive.getinfo("image/" + rel)
                with archive.open(info, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)

        for row in rows:
            target = staged / row["path"]
            if not target.is_file():
                raise RuntimeError(f"staged Forge Native image is missing: {row['path']}")
            if target.stat().st_size != int(row["bytes"]):
                raise RuntimeError(f"staged Forge Native update size mismatch: {row['path']}")
            if sha256(target).casefold() != str(row["sha256"]).casefold():
                raise RuntimeError(f"staged Forge Native update hash mismatch: {row['path']}")

        entrypoint = str(inspected["entrypoint"])
        if not (staged / entrypoint).is_file():
            raise RuntimeError(f"staged Forge Native image is missing entrypoint: {entrypoint}")

        plan = {
            "schema": "forge.native.update-stage.v1",
            "bridgeVersion": BRIDGE_VERSION,
            "state": "STAGED",
            "mode": mode,
            "transport": str(bundle),
            "transportSha256": inspected["transportSha256"],
            "currentRoot": str(current_root),
            "stagedRoot": str(staged),
            "maintenanceRoot": str(maintenance_root),
            "entrypoint": entrypoint,
            "applicationVersion": str(manifest.get("applicationVersion") or ""),
            "applicationBuild": str(manifest.get("applicationBuild") or ""),
            "fileCount": len(rows),
        }
        maintenance_root.mkdir(parents=True, exist_ok=True)
        plan_path = maintenance_root / "current-plan.json"
        plan["planJson"] = str(plan_path)
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        return plan
    except Exception:
        shutil.rmtree(staged, ignore_errors=True)
        raise


def build_bundle(
    image_root: Path,
    output: Path,
    entrypoint: str,
    application_version: str,
    application_build: str,
) -> dict[str, Any]:
    image_root = image_root.expanduser().resolve()
    output = output.expanduser().resolve()
    entrypoint = safe_relative(entrypoint)
    if not image_root.is_dir():
        raise FileNotFoundError(image_root)
    if not (image_root / entrypoint).is_file():
        raise RuntimeError(f"native application image is missing entrypoint: {entrypoint}")

    files: list[dict[str, Any]] = []
    total = 0
    for path in sorted(image_root.rglob("*")):
        if not path.is_file():
            continue
        rel = safe_relative(path.relative_to(image_root).as_posix())
        if rel.startswith("Data/") or rel in {".forge-portable", ".forgepy-portable"}:
            continue
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise RuntimeError(f"native application image file exceeds size policy: {rel}")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise RuntimeError("native application image exceeds total size policy")
        files.append({"path": rel, "bytes": size, "sha256": sha256(path)})
    if len(files) > MAX_FILES:
        raise RuntimeError(f"native application image exceeds {MAX_FILES} files")
    if entrypoint.casefold() not in {row["path"].casefold() for row in files}:
        raise RuntimeError("native update entrypoint was excluded from the governed image")

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "bridgeVersion": BRIDGE_VERSION,
        "applicationVersion": application_version,
        "applicationBuild": application_build,
        "entrypoint": entrypoint,
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2) + "\n")
        for row in files:
            archive.write(image_root / row["path"], "image/" + row["path"])
    inspect_bundle(output, expected_entrypoint=entrypoint)
    return {
        "schema": "forge.native.update-bundle-result.v1",
        "bundle": str(output),
        "sha256": sha256(output),
        "fileCount": len(files),
        "bytes": output.stat().st_size,
    }


def emit_result(row: dict[str, Any]) -> None:
    print("OK=1")
    for key, value in row.items():
        if key in {"schema", "bridgeVersion", "transportSha256", "fileCount", "bytes", "sha256"}:
            continue
        env_key = {
            "state": "STATE",
            "mode": "MODE",
            "transport": "TRANSPORT",
            "currentRoot": "CURRENT_ROOT",
            "stagedRoot": "STAGED_ROOT",
            "maintenanceRoot": "MAINTENANCE_ROOT",
            "entrypoint": "ENTRYPOINT",
            "applicationVersion": "APPLICATION_VERSION",
            "applicationBuild": "APPLICATION_BUILD",
            "planJson": "PLAN_JSON",
            "bundle": "BUNDLE",
        }.get(key)
        if env_key:
            print(f"{env_key}={value}")
    if "sha256" in row:
        print(f"SHA256={row['sha256']}")
    if "fileCount" in row:
        print(f"FILE_COUNT={row['fileCount']}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Forge Native SHADOW application-update verification bridge")
    sub = p.add_subparsers(dest="action", required=True)

    stage = sub.add_parser("stage")
    stage.add_argument("--transport", required=True)
    stage.add_argument("--current-root", required=True)
    stage.add_argument("--maintenance-root", required=True)
    stage.add_argument("--mode", required=True, choices=["development", "portable", "installed"])
    stage.add_argument("--entrypoint", required=True)

    build = sub.add_parser("build")
    build.add_argument("--image-root", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--entrypoint", required=True)
    build.add_argument("--application-version", required=True)
    build.add_argument("--application-build", required=True)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--transport", required=True)
    inspect.add_argument("--entrypoint")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = parser().parse_args(argv)
    try:
        if ns.action == "stage":
            result = stage_bundle(
                Path(ns.transport),
                Path(ns.current_root),
                Path(ns.maintenance_root),
                ns.mode,
                ns.entrypoint,
            )
            emit_result(result)
            return 0
        if ns.action == "build":
            result = build_bundle(
                Path(ns.image_root),
                Path(ns.output),
                ns.entrypoint,
                ns.application_version,
                ns.application_build,
            )
            emit_result(result)
            return 0
        if ns.action == "inspect":
            result = inspect_bundle(Path(ns.transport), ns.entrypoint)
            print(json.dumps({
                "schema": "forge.native.update-inspect.v1",
                "ok": True,
                "entrypoint": result["entrypoint"],
                "applicationVersion": result["manifest"].get("applicationVersion", ""),
                "applicationBuild": result["manifest"].get("applicationBuild", ""),
                "fileCount": len(result["files"]),
                "transportSha256": result["transportSha256"],
            }, indent=2))
            return 0
        raise RuntimeError(f"unsupported action: {ns.action}")
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
