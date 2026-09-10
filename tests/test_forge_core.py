from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ForgeHealth import evaluate_project
from ForgeIntake import counts_for_project, ingest_patch, list_items, reconcile_project, scan_downloads, scan_intake, stage_for_project
from ForgeSourceControl import status as source_status
from PCCSurfaceCommon import ProjectContract


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


def write_contract(root: Path, *, project_id: str = "demo", name: str = "Demo", provider: str = "") -> None:
    data = {
        "schema": "project.control.v1",
        "project": {"id": project_id, "name": name, "kind": "python", "build": "demo-build"},
        "commands": [
            {"key": "build", "label": "Build", "program": sys.executable, "args": ["-c", "print('build')"], "category": "build"},
            {"key": "patch.apply", "label": "Apply patches", "program": sys.executable, "args": ["-c", "print('patch')"], "category": "updates", "mutates": True},
        ],
    }
    if provider:
        data["root_control_center"] = {"machine_provider": provider}
    (root / "project.control.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_patch(path: Path, *, project: str = "Demo", patch_id: str = "DEMO-001") -> None:
    manifest = {
        "schema": "vault.patch.v2",
        "engine": "vault",
        "createdUtc": "2026-09-10T00:00:00Z",
        "preconditions": {"projectBuild": "demo-build"},
        "project": project,
        "patchId": patch_id,
        "title": "Forge intake smoke patch",
        "series": "demo",
        "sequence": 1,
        "files": [{"path": "README.txt", "bytes": 4, "sha256": "unused-by-intake"}],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PATCH_MANIFEST.json", json.dumps(manifest))
        zf.writestr("README.txt", "demo")


class ForgeCoreTests(unittest.TestCase):
    def test_health_for_operable_non_git_project(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_contract(root)
            health = evaluate_project(root, ProjectContract.load(root))
            self.assertEqual(health.level, "GREEN", health.reasons)

    def test_unassigned_legacy_queue_does_not_contaminate_project_health(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "Vault"
            project = base / "Project"; project.mkdir()
            write_contract(project, project_id="demo", name="Demo")
            transport = base / "Unassigned_Patch.zip"
            make_patch(transport, project="unassigned", patch_id="UNASSIGNED-001")
            with env(FORGE_VAULT_ROOT=str(vault), VAULT_INTAKE_PATHS=str(base / "Downloads")):
                item = ingest_patch(transport, remove_source=False, trusted_root=True)
                self.assertEqual(item["state"], "QUEUED")
                pending, invalid = counts_for_project("demo", "Demo")
                self.assertEqual((pending, invalid), (0, 0))
                health = evaluate_project(project, ProjectContract.load(project))
                self.assertEqual(health.level, "GREEN", health.reasons)

    def test_legacy_download_origin_queue_is_never_pending_or_stageable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            downloads = base / "Downloads"; downloads.mkdir()
            vault = base / "Vault"
            project = base / "Project"; project.mkdir()
            write_contract(project, project_id="demo", name="Demo")
            transport = downloads / "Demo_OldQueuedPatch.zip"
            make_patch(transport, project="Demo", patch_id="DEMO-OLD-DOWNLOAD")
            with env(FORGE_VAULT_ROOT=str(vault), FORGE_INTAKE_PATHS=str(downloads)):
                # Simulate the pre-F60R1 bug by explicitly ingesting a Downloads item as trusted.
                item = ingest_patch(transport, remove_source=False, trusted_root=True)
                self.assertEqual(item["state"], "QUEUED")
                self.assertEqual(counts_for_project("demo", "Demo"), (0, 0))
                staged = stage_for_project(project)
                self.assertEqual(staged["staged"], 0, staged)
                rows = list_items(project="Demo")
                self.assertEqual(rows[0]["state"], "AVAILABLE", rows)


    def test_explicit_patch_apply_stages_forge_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            downloads = base / "Downloads"; downloads.mkdir()
            vault = base / "Vault"
            project = base / "Project"; project.mkdir()
            provider = project / "provider.py"
            provider.write_text(
                """import argparse, json
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('command'); p.add_argument('--root', required=True); a=p.parse_args(); r=Path(a.root)
if a.command == 'patch-apply':
    receipts=r/'artifacts'/'patches'/'receipts'; receipts.mkdir(parents=True, exist_ok=True)
    for z in (r/'updates'/'inbox').glob('*.zip'):
        (receipts/'DEMO-003.json').write_text(json.dumps({'patchId':'DEMO-003','status':'applied'}))
        z.unlink(); Path(str(z)+'.sha256').unlink(missing_ok=True)
    print('[PASS] explicit patch apply'); raise SystemExit(0)
raise SystemExit(0)
""",
                encoding="utf-8",
            )
            write_contract(project, project_id="demo", name="Demo", provider="provider.py")
            transport = project / "Demo_Patch_003.zip"
            make_patch(transport, patch_id="DEMO-003")
            with env(FORGE_VAULT_ROOT=str(vault), FORGE_INTAKE_PATHS=str(downloads)):
                host = APP / "PCCOperationHost.py"
                cp = subprocess.run(
                    [sys.executable, str(host), "--root", str(project), "--operation", "patch-apply", "--", sys.executable, str(provider), "patch-apply", "--root", str(project)],
                    cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=os.environ.copy(), check=False,
                )
                self.assertEqual(cp.returncode, 0, cp.stdout)
                self.assertIn("explicit patch apply", cp.stdout)
                self.assertEqual(list_items(project="Demo")[0]["state"], "APPLIED", cp.stdout)

    def test_source_control_detects_github_and_forgejo(self) -> None:
        if not shutil_which("git"):
            self.skipTest("git unavailable")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "remote", "add", "origin", "https://github.com/example/demo.git"], cwd=root, check=True)
            subprocess.run(["git", "remote", "add", "forgejo", "http://127.0.0.1:3000/demo/demo.git"], cwd=root, check=True)
            state = source_status(root)
            self.assertTrue(state["gitReady"])
            self.assertTrue(state["githubConfigured"])
            self.assertTrue(state["forgejoConfigured"])

    def test_downloads_are_available_but_never_stageable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            downloads = base / "Downloads"; downloads.mkdir()
            vault = base / "Vault"
            project = base / "Project"; project.mkdir()
            write_contract(project, project_id="demo", name="Demo")
            transport = downloads / "Demo_Patch_001.zip"
            make_patch(transport)
            with env(FORGE_VAULT_ROOT=str(vault), FORGE_INTAKE_PATHS=str(downloads)):
                result = scan_downloads(force_stable=True, remove_source=True)
                self.assertEqual(len(result["ingested"]), 1, result)
                self.assertFalse(transport.exists())
                items = list_items(project="Demo")
                self.assertEqual(items[0]["state"], "AVAILABLE", items)
                self.assertIn("patches/available", items[0]["vault_path"].replace("\\", "/"))
                pending, invalid = counts_for_project("demo", "Demo")
                self.assertEqual((pending, invalid), (0, 0))
                staged = stage_for_project(project)
                self.assertEqual(staged["staged"], 0, staged)
                self.assertFalse((project / "updates" / "inbox" / "Demo_Patch_001.zip").exists())

    def test_operation_host_applies_vault_patch_before_build(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            downloads = base / "Downloads"; downloads.mkdir()
            vault = base / "Vault"
            project = base / "Project"; project.mkdir()
            provider = project / "provider.py"
            provider.write_text(
                """from __future__ import annotations
import argparse, json
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('command')
p.add_argument('--root', required=True)
a = p.parse_args()
r = Path(a.root)
if a.command == 'patch-apply':
    inbox = r / 'updates' / 'inbox'
    receipts = r / 'artifacts' / 'patches' / 'receipts'
    receipts.mkdir(parents=True, exist_ok=True)
    for z in inbox.glob('*.zip'):
        (receipts / 'DEMO-002.json').write_text(json.dumps({'patchId': 'DEMO-002', 'status': 'applied'}))
        z.unlink()
        Path(str(z) + '.sha256').unlink(missing_ok=True)
    print('[PASS] fake patch authority')
    raise SystemExit(0)
if a.command == 'build':
    print('[PASS] fake build')
    raise SystemExit(0)
print('[PASS] noop')
raise SystemExit(0)
""",
                encoding="utf-8",
            )
            write_contract(project, project_id="demo", name="Demo", provider="provider.py")
            transport = project / "Demo_Patch_002.zip"
            make_patch(transport, patch_id="DEMO-002")
            with env(FORGE_VAULT_ROOT=str(vault), FORGE_INTAKE_PATHS=str(downloads)):
                host = APP / "PCCOperationHost.py"
                cp = subprocess.run(
                    [sys.executable, str(host), "--root", str(project), "--operation", "build", "--", sys.executable, str(provider), "build", "--root", str(project)],
                    cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=os.environ.copy(), check=False,
                )
                self.assertEqual(cp.returncode, 0, cp.stdout)
                self.assertIn("fake patch authority", cp.stdout)
                self.assertIn("fake build", cp.stdout)
                items = list_items(project="Demo")
                self.assertEqual(items[0]["state"], "APPLIED", cp.stdout)


    def test_operation_host_does_not_poll_or_apply_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            downloads = base / "Downloads"; downloads.mkdir()
            vault = base / "Vault"
            project = base / "Project"; project.mkdir()
            provider = project / "provider.py"
            provider.write_text(
                """from __future__ import annotations
import argparse
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('command'); p.add_argument('--root', required=True); a=p.parse_args(); r=Path(a.root)
if a.command == 'patch-apply':
    print('[FAIL] downloads patch should never execute'); raise SystemExit(9)
if a.command == 'build':
    print('[PASS] build only'); raise SystemExit(0)
raise SystemExit(0)
""",
                encoding="utf-8",
            )
            write_contract(project, project_id="demo", name="Demo", provider="provider.py")
            transport = downloads / "Demo_Patch_004.zip"
            make_patch(transport, patch_id="DEMO-004")
            with env(FORGE_VAULT_ROOT=str(vault), FORGE_INTAKE_PATHS=str(downloads)):
                scan = scan_downloads(force_stable=True, remove_source=True)
                self.assertEqual(scan["ingested"][0]["state"], "AVAILABLE", scan)
                host = APP / "PCCOperationHost.py"
                cp = subprocess.run(
                    [sys.executable, str(host), "--root", str(project), "--operation", "build", "--", sys.executable, str(provider), "build", "--root", str(project)],
                    cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=os.environ.copy(), check=False,
                )
                self.assertEqual(cp.returncode, 0, cp.stdout)
                self.assertIn("[PASS] build only", cp.stdout)
                self.assertNotIn("downloads patch should never execute", cp.stdout)
                self.assertNotIn("Downloads intake", cp.stdout)
                self.assertEqual(list_items(project="Demo")[0]["state"], "AVAILABLE")
                self.assertFalse((project / "updates" / "inbox" / "Demo_Patch_004.zip").exists())


def shutil_which(name: str) -> str | None:
    import shutil
    return shutil.which(name)


if __name__ == "__main__":
    unittest.main()
