from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from PCCSurfaceCommon import ProjectRegistry
from VaultDriveIndex import scan as drive_scan
from VaultForgejo import doctor as forgejo_doctor, runner_token as forgejo_runner_token
from VaultIntake import scan_downloads
from VaultSettings import load_settings, save_settings
from VaultStorage import migrate_home, migrate_project


@contextmanager
def env(**values: str):
    old = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def write_project(root: Path, project_id: str = "demo") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.control.json").write_text(json.dumps({
        "schema": "project.control.v1",
        "project": {"id": project_id, "name": root.name, "kind": "python"},
        "commands": [{"key": "build.native", "label": "Build", "program": sys.executable, "args": ["-c", "print('[PASS] build')"]}],
        "quality_gates": [{"key": "gate.full"}],
    }), encoding="utf-8")


def write_invalid_patch(path: Path) -> None:
    manifest = {
        "schema": "vault.patch.v2",
        "engine": "vault",
        "createdUtc": "2026-09-10T00:00:00Z",
        "preconditions": {"projectBuild": "demo-build"},
        "project": "demo",
        "patchId": "bad patch id with spaces",
        "files": [],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PATCH_MANIFEST.json", json.dumps(manifest))


class VaultF21F40Tests(unittest.TestCase):
    def test_download_rejection_is_review_only_for_project_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            downloads = base / "Downloads"; downloads.mkdir()
            project = base / "Project"; write_project(project)
            write_invalid_patch(downloads / "bad.zip")
            child = project / "gate.py"
            child.write_text("print('[PASS] project gate'); raise SystemExit(0)\n", encoding="utf-8")
            host = APP / "PCCOperationHost.py"
            run_env = os.environ.copy()
            run_env.update({"VAULT_STORAGE_ROOT": str(base / "Library"), "VAULT_INTAKE_PATHS": str(downloads)})
            cp = subprocess.run(
                [sys.executable, str(host), "--root", str(project), "--operation", "full", "--", sys.executable, str(child)],
                cwd=project, env=run_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout)
            self.assertIn("[PASS] project gate", cp.stdout)
            self.assertTrue((downloads / "bad.zip").is_file(), cp.stdout)

    def test_unchanged_rejected_download_is_suppressed_after_first_observation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            downloads = base / "Downloads"; downloads.mkdir()
            write_invalid_patch(downloads / "bad.zip")
            with env(VAULT_STORAGE_ROOT=str(base / "Library"), VAULT_INTAKE_PATHS=str(downloads)):
                first = scan_downloads(force_stable=True, remove_source=False)
                second = scan_downloads(force_stable=True, remove_source=False)
            self.assertEqual(len(first["errors"]), 0, first)
            self.assertEqual(len(first["skipped"]), 1, first)
            self.assertIn("retained for review", first["skipped"][0]["reason"])
            self.assertEqual(len(second["errors"]), 0, second)
            self.assertEqual(len(second["skipped"]), 1, second)
            self.assertIn("unchanged previously rejected", second["skipped"][0]["reason"])

    def test_drive_index_finds_nested_composite_projects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            scan_root = base / "DriveD"; scan_root.mkdir()
            parent = scan_root / "Workspace"; parent.mkdir()
            (parent / "Cargo.toml").write_text("[workspace]\nmembers=['child']\n", encoding="utf-8")
            child = parent / "child"; child.mkdir()
            (child / "Cargo.toml").write_text("[package]\nname='child'\nversion='0.1.0'\n", encoding="utf-8")
            with env(VAULT_STORAGE_ROOT=str(base / "Library")):
                result = drive_scan(scan_root, max_depth=5, max_dirs=1000)
            roots = {Path(row["root"]).resolve() for row in result["records"]}
            self.assertIn(parent.resolve(), roots)
            self.assertIn(child.resolve(), roots)
            child_row = next(row for row in result["records"] if Path(row["root"]).resolve() == child.resolve())
            self.assertEqual(Path(child_row["parentRoot"]).resolve(), parent.resolve())

    def test_vault_home_migration_is_hash_verified_and_keeps_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            settings_path = base / "settings.json"
            old_home = base / "OldVault"; old_home.mkdir()
            (old_home / "catalog").mkdir()
            (old_home / "catalog" / "x.txt").write_text("vault-data", encoding="utf-8")
            new_home = base / "NewVault"
            with env(VAULT_SETTINGS_PATH=str(settings_path)):
                save_settings({"vaultHome": str(old_home), "projectsRoot": str(base / "Projects"), "scanRoots": [str(base)]})
                result = migrate_home(old_home, new_home)
                settings = load_settings()
            self.assertEqual(result["status"], "migrated")
            self.assertTrue((old_home / "catalog" / "x.txt").is_file())
            self.assertEqual((new_home / "catalog" / "x.txt").read_text(encoding="utf-8"), "vault-data")
            self.assertEqual(Path(settings["vaultHome"]).resolve(), new_home.resolve())
            self.assertTrue(Path(result["receipt"]).is_file())

    def test_verified_project_migration_rebinds_stable_registry_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            settings_path = base / "settings.json"
            registry_path = base / "registry.json"
            source = base / "Desktop" / "Demo"
            write_project(source, "portable-demo")
            (source / "assets").mkdir()
            (source / "assets" / "sprite.bin").write_bytes(b"portable-assets")
            projects = base / "DProjects"
            vault_home = base / "Vault"
            with env(VAULT_SETTINGS_PATH=str(settings_path)):
                save_settings({"vaultHome": str(vault_home), "projectsRoot": str(projects), "scanRoots": [str(projects)]})
                registry = ProjectRegistry(registry_path)
                original = registry.register(source, make_active=True)
                result = migrate_project(source, projects)
                target = Path(result["target"])
                relocated = registry.relocate(source, target, make_active=True)
                entries = registry.entries()
            self.assertEqual(relocated.registry_id, original.registry_id)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].root.resolve(), target.resolve())
            self.assertTrue(source.is_dir(), "source must remain as rollback evidence")
            self.assertEqual((target / "assets" / "sprite.bin").read_bytes(), b"portable-assets")
            self.assertTrue(Path(result["receipt"]).is_file())
            self.assertEqual(result["files"], result["verifiedFiles"])

    def test_project_registry_rebinds_portable_project_after_projects_root_move(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            settings_path = base / "settings.json"
            registry_path = base / "registry.json"
            a = base / "AProjects"; b = base / "BProjects"
            project_a = a / "Family" / "Demo"; write_project(project_a, "portable-demo")
            with env(VAULT_SETTINGS_PATH=str(settings_path)):
                save_settings({"vaultHome": str(base / "Vault"), "projectsRoot": str(a), "scanRoots": [str(a)]})
                registry = ProjectRegistry(registry_path)
                registered = registry.register(project_a)
                project_b = b / "Family" / "Demo"
                project_b.parent.mkdir(parents=True)
                shutil.copytree(project_a, project_b)
                shutil.rmtree(a)
                save_settings({"vaultHome": str(base / "Vault"), "projectsRoot": str(b), "scanRoots": [str(b)]})
                entries = ProjectRegistry(registry_path).entries()
            row = next(x for x in entries if x.registry_id == registered.registry_id)
            self.assertEqual(row.root.resolve(), project_b.resolve())

    def test_forgejo_commands_match_v16_cli_shapes(self) -> None:
        with mock.patch("VaultForgejo._run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="ok")
            forgejo_doctor(all_checks=False)
            run.assert_called_with("doctor", "check", "--log-file", "-", "--default", timeout=300.0)
        with mock.patch("VaultForgejo._run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="token")
            forgejo_runner_token("owner/repo")
            run.assert_called_with("forgejo-cli", "actions", "generate-runner-token", "--scope", "owner/repo", timeout=90.0)


if __name__ == "__main__":
    unittest.main()
