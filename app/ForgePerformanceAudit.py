#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

AUDIT_VERSION = "FORGEPY-PERFORMANCE-AUDIT-1.0-F556"
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "target",
    "build", "builds", "bin", "obj", ".vs", ".idea", "artifacts", "logs",
}
MAX_FILES = 20000


@dataclass(frozen=True)
class Finding:
    severity: str
    kind: str
    path: str
    line: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _iter_python(root: Path):
    seen = 0
    for base, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name.casefold() not in SKIP_DIRS]
        base_path = Path(base)
        for name in files:
            if not name.endswith(".py"):
                continue
            yield base_path / name
            seen += 1
            if seen >= MAX_FILES:
                return


def _call_name(node: ast.Call) -> str:
    parts: list[str] = []
    value: ast.AST = node.func
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


class Visitor(ast.NodeVisitor):
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.findings: list[Finding] = []
        self.loop_depth = 0
        self.function_stack: list[str] = []

    def _add(self, severity: str, kind: str, node: ast.AST, message: str) -> None:
        self.findings.append(Finding(severity, kind, self.rel, int(getattr(node, "lineno", 0) or 0), message))

    def visit_For(self, node: ast.For) -> Any:
        self.loop_depth += 1
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_While(self, node: ast.While) -> Any:
        self.loop_depth += 1
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call) -> Any:
        name = _call_name(node)
        low = name.casefold()
        fn = self.function_stack[-1] if self.function_stack else ""

        if low.endswith("os.walk") or low == "os.walk":
            self._add("WARN", "recursive-scan", node, f"Recursive filesystem walk in {fn or '<module>'}; keep off Tk and coordinate I/O.")
        elif low.endswith(".rglob") or low == "path.rglob":
            self._add("WARN", "recursive-scan", node, f"Recursive rglob in {fn or '<module>'}; prefer indexed/cached data in UI paths.")

        if low in {"subprocess.run", "subprocess.check_output", "subprocess.check_call", "subprocess.call"}:
            timeout_present = any(keyword.arg == "timeout" for keyword in node.keywords)
            self._add(
                "WARN" if timeout_present else "HIGH",
                "subprocess",
                node,
                "Synchronous subprocess call" + (" with timeout." if timeout_present else " without timeout."),
            )
        elif low == "subprocess.popen":
            self._add("INFO", "subprocess-stream", node, "Streaming subprocess creation; verify wait/read occurs off Tk.")

        if low.endswith("read_bytes") and self.loop_depth:
            self._add("HIGH", "bulk-read-loop", node, "Whole-file read_bytes() inside a loop can create memory/I/O spikes.")

        if low in {"threading.thread", "thread"}:
            self._add("INFO", "raw-thread", node, "Raw thread creation bypasses centralized job/load scheduling.")
        elif low.endswith("threadpoolexecutor"):
            self._add("INFO", "thread-pool", node, "Independent ThreadPoolExecutor; review against global load coordination.")

        if self.function_stack and any(token in fn.casefold() for token in ("selection", "show_app", "show_page", "build_", "click")):
            if any(token in low for token in ("projectcontract.load", "backendclient", "status_payload", "source_status", "repo_hygiene", "scan_project")):
                self._add("HIGH", "ui-hot-path", node, f"Potential heavy operation in GUI hot function {fn}.")

        self.generic_visit(node)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audit(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    started = time.monotonic()
    findings: list[Finding] = []
    parsed = 0
    parse_errors = 0

    for path in _iter_python(root):
        rel = path.relative_to(root).as_posix()
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size >= 200_000:
            findings.append(Finding(
                "HIGH", "large-module", rel, 0,
                f"Python module is {size:,} bytes; large GUI/runtime monoliths increase import coupling and regression risk."
            ))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=rel)
            parsed += 1
        except SyntaxError as exc:
            parse_errors += 1
            findings.append(Finding("HIGH", "syntax", rel, int(exc.lineno or 0), str(exc)))
            continue
        visitor = Visitor(rel)
        visitor.visit(tree)
        findings.extend(visitor.findings)

    # Root app vs nested ForgePY/app duplication is architectural debt even when identical.
    canonical = root / "app"
    mirror = root / "ForgePY" / "app"
    duplicates: list[dict[str, Any]] = []
    if canonical.is_dir() and mirror.is_dir():
        for left in canonical.glob("*.py"):
            right = mirror / left.name
            if not right.is_file():
                continue
            try:
                same = left.stat().st_size == right.stat().st_size and _sha(left) == _sha(right)
            except OSError:
                same = False
            duplicates.append({"path": left.name, "same": same})
            findings.append(Finding(
                "WARN" if same else "HIGH",
                "duplicate-source-authority",
                f"app/{left.name}",
                0,
                "Canonical root app/ has a nested ForgePY/app mirror "
                + ("with identical content." if same else "with divergent content; this can package or execute the wrong implementation."),
            ))

    counts: dict[str, int] = {}
    severities: dict[str, int] = {}
    for finding in findings:
        counts[finding.kind] = counts.get(finding.kind, 0) + 1
        severities[finding.severity] = severities.get(finding.severity, 0) + 1

    ordered = sorted(
        findings,
        key=lambda x: (
            {"HIGH": 0, "WARN": 1, "INFO": 2}.get(x.severity, 9),
            x.path.casefold(), x.line, x.kind,
        ),
    )
    return {
        "schema": "forgepy.performance-audit.v1",
        "version": AUDIT_VERSION,
        "root": str(root),
        "elapsedMs": round((time.monotonic() - started) * 1000.0, 1),
        "pythonFilesParsed": parsed,
        "parseErrors": parse_errors,
        "findingCount": len(ordered),
        "severityCounts": severities,
        "kindCounts": counts,
        "duplicateAppMirror": duplicates,
        "findings": [item.to_dict() for item in ordered],
        "architecturalRules": [
            "Tk callbacks must not perform recursive filesystem scans, Git/subprocess probes, hashing, or project discovery.",
            "Project selection is preview-only; project activation is asynchronous.",
            "Recursive scanners share one coordinated I/O lane.",
            "Routine UI status uses cached fast source state; exact GREEN fingerprinting belongs to certification/source operations.",
            "GUI, CLI, headless and Cortex consume the same operation/capability services.",
        ],
    }


def _markdown(data: dict[str, Any]) -> str:
    lines = [
        "# ForgePY Performance & Reliability Audit",
        "",
        f"- Root: `{data['root']}`",
        f"- Parsed Python files: {data['pythonFilesParsed']}",
        f"- Findings: {data['findingCount']}",
        f"- Audit time: {data['elapsedMs']} ms",
        "",
        "## Severity",
        "",
    ]
    for key in ("HIGH", "WARN", "INFO"):
        lines.append(f"- {key}: {int((data.get('severityCounts') or {}).get(key, 0))}")
    lines += ["", "## Findings", ""]
    for item in data.get("findings", [])[:500]:
        where = f"{item['path']}:{item['line']}" if item.get("line") else item["path"]
        lines.append(f"- **{item['severity']} · {item['kind']}** — `{where}` — {item['message']}")
    if len(data.get("findings", [])) > 500:
        lines.append(f"- … {len(data['findings']) - 500} additional findings remain in JSON.")
    return "\n".join(lines) + "\n"


def write_report(root: Path) -> dict[str, Any]:
    data = audit(root)
    project_id = root.name
    try:
        from PCCSurfaceCommon import ProjectContract
        project_id = ProjectContract.load(root).project_id
    except Exception:
        pass
    try:
        from ForgePYPaths import ensure_artifact_project_tree
        target = Path(ensure_artifact_project_tree(project_id)["reports"]) / "performance"
    except Exception:
        target = root / "artifacts" / "performance"
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "performance-audit.json"
    md_path = target / "performance-audit.md"
    json_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(data), encoding="utf-8")
    return {**data, "jsonPath": str(json_path), "markdownPath": str(md_path)}
