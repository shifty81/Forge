#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path, PurePosixPath
from typing import Iterable

PACKAGE_POLICY_VERSION = "FORGEPY-PACKAGE-POLICY-1.0"

# These are machine/runtime state. They are intentionally never part of a
# distributable package diff or a ForgePY self-update preimage contract.
TRANSIENT_TOP_LEVEL = {
    ".git", ".forge", "__pycache__", "logs", "artifacts", "updates",
    "hotfix-backups", "dist", "build", "installer-staging",
}
TRANSIENT_FILE_NAMES = {
    "forgepy.settings.json", "forge.settings.json", "vault.settings.json",
}
TRANSIENT_SUFFIXES = {".pyc", ".pyo", ".dmp", ".mdmp"}


def normalize_rel(path: str | Path) -> str:
    raw=str(path).replace("\\", "/").strip("/")
    if not raw:
        return ""
    p=PurePosixPath(raw)
    return "/".join(p.parts)


def classification(path: str | Path) -> str:
    rel=normalize_rel(path)
    if not rel:
        return "invalid"
    p=PurePosixPath(rel)
    folded=[part.casefold() for part in p.parts]
    if folded and folded[0] in {x.casefold() for x in TRANSIENT_TOP_LEVEL}:
        return "runtime-transient"
    if p.name.casefold() in {x.casefold() for x in TRANSIENT_FILE_NAMES}:
        return "machine-local"
    if p.suffix.casefold() in TRANSIENT_SUFFIXES:
        return "runtime-transient"
    return "governed"


def is_governed(path: str | Path) -> bool:
    return classification(path) == "governed"


def self_update_safe(path: str | Path) -> bool:
    return is_governed(path)


def filter_governed(paths: Iterable[str | Path]) -> list[str]:
    return [normalize_rel(p) for p in paths if is_governed(p)]
