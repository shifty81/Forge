from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from PCCProjectDiscovery import discover_project_contract_data, discovery_summary
from PCCSurfaceCommon import BackendClient, ProjectContract
from PCCVaultCatalog import scan_project
from VaultIntake import list_items, scan_intake
from VaultPatchEngine import apply_inbox, restart_marker_path


@contextmanager
def env(**values: str):
    old = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def make_universal_patch(path: Path, *, project: str, patch_id: str, rel: str, before: bytes | None, after: bytes) -> None:
    row = {
        "path": rel,
        "operation": "write",
        "sha256": hashlib.sha256(after).hexdigest(),
        "bytes": len(after),
    }
    if before is not None:
        row["preSha256"] = hashlib.sha256(before).hexdigest()
    manifest = {
        "schema": "forge.patch.v1",
        "engine": "forge-universal",
        "createdUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "preconditions": {"projectBuild": "demo-build"},
        "project": project,
        "patchId": patch_id,
        "title": "Forge universal patch test",
        "files": [row],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PATCH_MANIFEST.json", json.dumps(manifest, indent=2))
        zf.writestr(f"payload/{rel}", after)


class VaultCoreTests(unittest.TestCase):
    def test_stardew_nested_tooling_is_executable_not_scan_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "SDMODDING"
            script = root / "tools" / "control" / "StardewModdingKitTools.ps1"
            script.parent.mkdir(parents=True)
            script.write_text(
                """param(\n[ValidateSet('Environment','Build','Full-Gate','Run-Game','Package')]\n[string]$Action='Environment'\n)\nWrite-Host $Action\n""",
                encoding="utf-8",
            )
            data = discover_project_contract_data(root)
            keys = {str(row.get("key")) for row in data.get("commands", [])}
            self.assertEqual(data["project"]["kind"], "stardew-toolkit")
            self.assertIn("build.native", keys)
            self.assertIn("gate.full", keys)
            self.assertIn("run.game", keys)
            self.assertEqual(data["root_control_center"]["discoveredPowerShell"], "tools/control/StardewModdingKitTools.ps1")
            backend = BackendClient(root, ProjectContract.load(root))
            self.assertTrue(backend.supports("build"))
            self.assertTrue(backend.supports("full"))

    def test_dotnet_project_gets_build_and_gate_commands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Example.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"></Project>', encoding="utf-8")
            data = discover_project_contract_data(root)
            keys = {str(row.get("key")) for row in data.get("commands", [])}
            self.assertEqual(data["project"]["kind"], "dotnet")
            self.assertIn("build.native", keys)
            self.assertIn("build.release", keys)
            self.assertIn("gate.full", keys)

    def test_vault_scan_reports_discovered_tooling_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "Project"; root.mkdir()
            (root / "Example.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"></Project>', encoding="utf-8")
            (root / "Program.cs").write_text("class Program {}\n", encoding="utf-8")
            with env(VAULT_STORAGE_ROOT=str(base / "Library")):
                summary = scan_project(root)
            tooling = summary.get("tooling") or {}
            self.assertTrue(tooling.get("buildCapable"), tooling)
            self.assertTrue(tooling.get("gateCapable"), tooling)
            self.assertGreaterEqual(int(tooling.get("commandCount") or 0), 2)
            self.assertEqual((summary.get("projectDiscovery") or {}).get("kind"), "dotnet")

    def test_root_drop_ingests_but_build_does_not_implicitly_apply(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            project = base / "Demo"; project.mkdir()
            library = base / "Library"
            target = project / "hello.txt"
            before = b"before\n"; after = b"after\n"
            target.write_bytes(before)
            provider = project / "provider.py"
            provider.write_text("import sys; print('[PASS] build'); raise SystemExit(0)\n", encoding="utf-8")
            contract = {
                "schema": "forge.project.v1",
                "project": {"id": "demo", "name": "Demo", "kind": "python", "build": "demo-build"},
                "commands": [{"key": "build.native", "label": "Build", "program": sys.executable, "args": [str(provider)]}],
            }
            (project / "project.control.json").write_text(json.dumps(contract), encoding="utf-8")
            patch = project / "incoming.patch"
            make_universal_patch(patch, project="Demo", patch_id="DEMO-VAULT-001", rel="hello.txt", before=before, after=after)
            with env(VAULT_STORAGE_ROOT=str(library), VAULT_INTAKE_PATHS=str(base / "Downloads")):
                result = scan_intake(extra_roots=(project,), force_stable=True, remove_source=True)
                self.assertEqual(len(result["ingested"]), 1, result)
                self.assertFalse(patch.exists())
                # Apply directly from Artifact Central through the real operation host.
                host = APP / "PCCOperationHost.py"
                cp = subprocess.run(
                    [sys.executable, str(host), "--root", str(project), "--operation", "build", "--", sys.executable, str(provider)],
                    cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=os.environ.copy(), check=False,
                )
                self.assertEqual(cp.returncode, 0, cp.stdout)
                self.assertEqual(target.read_bytes(), before, cp.stdout)
                states = {x["patch_id"]: x["state"] for x in list_items()}
                self.assertEqual(states.get("DEMO-VAULT-001"), "QUEUED", cp.stdout)

    def test_universal_patch_preimage_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            project = base / "Demo"; project.mkdir()
            inbox = project / "updates" / "inbox"; inbox.mkdir(parents=True)
            target = project / "hello.txt"
            target.write_bytes(b"unexpected\n")
            make_universal_patch(inbox / "bad.zip", project="Demo", patch_id="DEMO-BAD-001", rel="hello.txt", before=b"expected\n", after=b"new\n")
            with env(VAULT_STORAGE_ROOT=str(base / "Library")):
                with self.assertRaises(Exception):
                    apply_inbox(project)
            self.assertEqual(target.read_bytes(), b"unexpected\n")


if __name__ == "__main__":
    unittest.main()
