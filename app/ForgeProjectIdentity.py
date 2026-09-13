#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from typing import Any

IDENTITY_VERSION = "FORGEPY-PROJECT-IDENTITY-1.0-F700"

def _json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def resolve(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    result = {
        "schema": "forgepy.project-identity.v1",
        "versionSchema": IDENTITY_VERSION,
        "name": root.name,
        "projectId": root.name.casefold(),
        "projectVersion": "",
        "projectBuild": "",
        "kind": "",
        "source": "",
    }
    control = root / "project.control.json"
    if control.is_file():
        data = _json(control)
        project = data.get("project") if isinstance(data.get("project"), dict) else {}
        result.update({
            "name": str(project.get("name") or result["name"]),
            "projectId": str(project.get("id") or result["projectId"]),
            "projectVersion": str(project.get("version") or ""),
            "projectBuild": str(project.get("build") or ""),
            "kind": str(project.get("kind") or ""),
            "source": "project.control.json",
        })
    if str(result["projectId"]).casefold() == "forgepy" or root.name.casefold() == "forgepy":
        try:
            from ForgeApplicationIdentity import DISPLAY_VERSION, DISPLAY_BUILD
            result["projectVersion"] = DISPLAY_VERSION
            result["projectBuild"] = DISPLAY_BUILD
            result["source"] = "ForgeApplicationIdentity"
            return result
        except Exception:
            pass
    if not result["projectVersion"]:
        package = root / "package.json"
        if package.is_file():
            data = _json(package)
            result["projectVersion"] = str(data.get("version") or "")
            result["source"] = result["source"] or "package.json"
    if not result["projectVersion"]:
        for filename, section in (("pyproject.toml", None), ("Cargo.toml", "[package]")):
            path = root / filename
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:131072]
                if section and section in text:
                    text = text.split(section, 1)[1]
                match = re.search(r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']', text)
                if match:
                    result["projectVersion"] = match.group(1).strip()
                    result["source"] = result["source"] or filename
                    break
            except Exception:
                pass
    for name in ("VERSION", "version.txt", "VERSION.txt"):
        path = root / name
        if not result["projectVersion"] and path.is_file():
            try:
                value = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[0][:128]
                if value:
                    result["projectVersion"] = value
                    result["source"] = result["source"] or name
            except Exception:
                pass
    return result

def label(root: Path) -> str:
    row = resolve(root)
    name = str(row.get("name") or root.name)
    identity = str(row.get("projectBuild") or row.get("projectVersion") or "").strip()
    return f"{name} · {identity}" if identity else name
