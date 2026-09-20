#!/usr/bin/env python3
from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any, Callable

from ForgeOperationEnvelope import OperationTranscript
from ForgeProjectAudit import audit as audit_project, write_handoffs
from ForgeProjectProtocol import effective_capabilities, normalize_key, provider_command
from PCCSurfaceCommon import BackendClient, ProjectContract, ProjectRegistry

SERVICES_VERSION = "FORGEPY-UNIFIED-SERVICES-1.2-F605"
OUTPUT_TAIL_LIMIT = 5000


class ForgeVaultService:
    def workflow(self) -> dict[str, Any]:
        from ForgeVaultWorkflow import workflow
        return workflow()

    def projects(self) -> list[dict[str, Any]]:
        rows = []
        for entry in ProjectRegistry().entries():
            rows.append({
                "registryId": entry.registry_id,
                "projectId": entry.project_id,
                "name": entry.name,
                "kind": entry.kind,
                "root": str(entry.root),
                "github": entry.github_url,
            })
        return rows

    def queue_patch(self, source: Path) -> dict[str, Any]:
        from ForgePYIntake import queue_manual_patch
        return queue_manual_patch(source)


class ForgeProjectService:
    def audit(self, root: Path, *, deep: bool = False) -> dict[str, Any]:
        return audit_project(root, deep=deep)

    def handoffs(self, root: Path, *, deep: bool = False) -> dict[str, Any]:
        return write_handoffs(root, deep=deep)

    def capabilities(self, root: Path) -> list[str]:
        contract = ProjectContract.load(root)
        project_keys = [item.key for item in contract.commands]
        return sorted(effective_capabilities(project_keys))


class ForgeOperationService:

    def _direct(
        self,
        root: Path,
        contract: ProjectContract,
        canonical: str,
        transcript: OperationTranscript,
        emit: Callable[[dict[str, Any]], None] | None,
    ) -> dict[str, Any] | None:
        """Handle universal read/service commands without pretending the project provider owns them."""
        value: Any
        if canonical == "source.status":
            from ForgePYSourceControl import status
            value = status(root)
        elif canonical == "project.audit":
            value = audit_project(root, deep=False)
        elif canonical == "artifacts.list":
            try:
                from ForgeArtifactIndex import search
                value = search(project_id=contract.project_id, limit=250)
            except TypeError:
                try:
                    from ForgeArtifactIndex import search
                    value = search(contract.project_id)
                except Exception as exc:
                    value = {"error": str(exc)}
        else:
            return None

        if isinstance(value, dict) and value.get("error"):
            error = str(value["error"])
            event = transcript.emit("diagnostic.error", error)
            if emit:
                emit(event.to_dict())
            result = transcript.finish(ok=False, returncode=8, result=value, error=error)
            if emit:
                emit(result["events"][-1])
            return result
        event = transcript.emit("operation.result", canonical, result=value)
        if emit:
            emit(event.to_dict())
        result = transcript.finish(ok=True, returncode=0, result=value)
        if emit:
            emit(result["events"][-1])
        return result

    def run(
        self,
        root: Path,
        command: str,
        *,
        extra: list[str] | None = None,
        initiator: str = "cli",
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        root = root.expanduser().resolve()
        contract = ProjectContract.load(root)
        canonical = normalize_key(command)
        transcript = OperationTranscript(contract.project_id, canonical, initiator=initiator)
        started_event = transcript.emit("operation.started", canonical)
        if emit:
            emit(started_event.to_dict())

        direct = self._direct(root, contract, canonical, transcript, emit)
        if direct is not None:
            return direct

        provider = provider_command(canonical)
        backend = BackendClient(root, contract)
        if not backend.supports(provider):
            result = transcript.finish(ok=False, returncode=2, error=f"command unavailable: {canonical}")
            if emit:
                emit(result["events"][-1])
            return result

        from ForgeOperationGuard import GUARD
        cooldown = 2.0 if canonical == "diagnostics.bundle" else 0.0
        lease = GUARD.acquire(contract.project_id, canonical, cooldown=cooldown)
        if lease is None:
            result = transcript.finish(ok=False, returncode=3, error=f"operation already active or recently completed: {canonical}")
            if emit:
                emit(result["events"][-1])
            return result
        proc = None
        lines: deque[str] = deque(maxlen=OUTPUT_TAIL_LIMIT)
        line_count = 0
        try:
            proc = backend.popen(provider, extra or [])
            assert proc.stdout is not None
            for line in proc.stdout:
                text = line.rstrip("\r\n")
                line_count += 1
                lines.append(text)
                event_type = "output"
                upper = text.upper()
                if "[FAIL]" in upper or upper.startswith("FAIL"):
                    event_type = "diagnostic.error"
                elif "[WARN]" in upper or upper.startswith("WARN"):
                    event_type = "diagnostic.warning"
                elif "[PASS]" in upper or upper.startswith("PASS"):
                    event_type = "diagnostic.pass"
                event = transcript.emit(event_type, text)
                if emit:
                    emit(event.to_dict())
            rc = int(proc.wait())
            retained = list(lines)
            return transcript.finish(
                ok=(rc == 0),
                returncode=rc,
                result={
                    "lines": retained,
                    "lineCount": line_count,
                    "linesDropped": max(0, line_count - len(retained)),
                },
            )
        finally:
            GUARD.release(lease)


vault = ForgeVaultService()
project = ForgeProjectService()
operations = ForgeOperationService()
