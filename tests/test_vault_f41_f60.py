from __future__ import annotations

import json
import os
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

from VaultArtifacts import archive_file
from VaultBuildIdentity import build_identity
from VaultComponents import inventory as component_inventory
from VaultIde import confined
from VaultIntake import inspect_patch, list_items, scan_downloads, scan_intake
from VaultSettings import load_settings, save_settings
from VaultTooling import audit_project
from VaultTray import DEFAULT_MENU


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


def write_patch(path: Path, manifest: dict) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PATCH_MANIFEST.json", json.dumps(manifest, indent=2))


class VaultF41F60Tests(unittest.TestCase):
    def test_modern_patch_requires_date_and_build_binding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            settings = base / "settings.json"
            with env(VAULT_SETTINGS_PATH=str(settings)):
                save_settings({"vaultHome": str(base / "Vault"), "security": {"strictModernPatches": True, "requireModernBuildBinding": True}})
                missing_date = base / "missing_date.zip"
                write_patch(missing_date, {"schema": "vault.patch.v2", "engine": "vault", "project": "demo", "patchId": "DEMO-001", "preconditions": {"projectBuild": "B1"}, "files": []})
                with self.assertRaisesRegex(Exception, "createdUtc"):
                    inspect_patch(missing_date)
                missing_binding = base / "missing_binding.zip"
                write_patch(missing_binding, {"schema": "vault.patch.v2", "engine": "vault", "project": "demo", "patchId": "DEMO-002", "createdUtc": datetime.now(timezone.utc).isoformat(), "files": []})
                with self.assertRaisesRegex(Exception, "build/source identity"):
                    inspect_patch(missing_binding)

    def test_legacy_download_patch_is_retained_for_review_not_autoqueued(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); downloads = base / "Downloads"; downloads.mkdir(); settings = base / "settings.json"
            patch = downloads / "Old_Project_Patch.zip"
            write_patch(patch, {"schema": "vault.patch.v1", "engine": "vault", "project": "demo", "patchId": "old patch id", "files": []})
            with env(VAULT_SETTINGS_PATH=str(settings), VAULT_STORAGE_ROOT=str(base / "Library"), VAULT_ARTIFACT_CENTRAL_ROOT=str(base / "Artifacts"), VAULT_INTAKE_PATHS=str(downloads)):
                save_settings({"vaultHome": str(base / "Vault"), "artifactCentralRoot": str(base / "Artifacts"), "security": {"legacyPatchPolicy": "review"}})
                result = scan_downloads(force_stable=True, remove_source=True)
                rows = list_items(project="demo")
            self.assertEqual(result["errors"], [], result)
            self.assertEqual(rows[0]["state"], "REVIEW", rows)
            self.assertFalse(patch.exists())
            self.assertTrue(Path(rows[0]["vault_path"]).is_file())
            self.assertIn("review", Path(rows[0]["vault_path"]).parts)

    def test_modern_download_patch_is_available_not_queued(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); downloads=base/"Downloads"; downloads.mkdir(); project=base/"Demo"; project.mkdir(); settings=base/"settings.json"
            (project/"project.control.json").write_text(json.dumps({"project":{"id":"demo","name":"Demo","build":"B1","version":"1.0"},"commands":[]}),encoding="utf-8")
            patch=downloads/"Demo_Patch_005.zip"
            write_patch(patch,{"schema":"vault.patch.v2","engine":"vault","project":"Demo","patchId":"DEMO-005","createdUtc":datetime.now(timezone.utc).isoformat(),"preconditions":{"projectBuild":"B1"},"files":[]})
            with env(VAULT_SETTINGS_PATH=str(settings),VAULT_STORAGE_ROOT=str(base/"Library"),VAULT_ARTIFACT_CENTRAL_ROOT=str(base/"Artifacts"),VAULT_INTAKE_PATHS=str(downloads)):
                save_settings({"vaultHome":str(base/"Vault"),"artifactCentralRoot":str(base/"Artifacts")})
                result=scan_downloads(force_stable=True,remove_source=True)
                rows=list_items(project="Demo")
            self.assertEqual(result["errors"],[],result)
            self.assertEqual(rows[0]["state"],"AVAILABLE",rows)
            self.assertFalse(patch.exists())
            self.assertIn("available",Path(rows[0]["vault_path"]).parts)

    def test_rejected_download_transport_moves_to_inert_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); downloads=base/"Downloads"; downloads.mkdir(); settings=base/"settings.json"
            bad=downloads/"Demo_Patch_Bad.zip"
            write_patch(bad,{"schema":"vault.patch.v2","engine":"vault","project":"Demo","patchId":"x","createdUtc":datetime.now(timezone.utc).isoformat(),"preconditions":{"projectBuild":"B1"},"files":[]})
            with env(VAULT_SETTINGS_PATH=str(settings),VAULT_STORAGE_ROOT=str(base/"Library"),VAULT_ARTIFACT_CENTRAL_ROOT=str(base/"Artifacts"),VAULT_INTAKE_PATHS=str(downloads)):
                save_settings({"vaultHome":str(base/"Vault"),"artifactCentralRoot":str(base/"Artifacts")})
                result=scan_downloads(force_stable=True,remove_source=True)
            self.assertEqual(result["errors"],[],result)
            self.assertEqual(len(result["reviews"]),1,result)
            self.assertFalse(bad.exists())
            self.assertEqual(result["reviews"][0]["state"],"REVIEW")
            self.assertTrue(Path(result["reviews"][0]["vault_path"]).is_file())

    def test_legacy_project_root_drop_remains_deliberate_compatibility_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); project=base/"Demo"; project.mkdir(); downloads=base/"Downloads"; downloads.mkdir(); settings=base/"settings.json"
            patch=project/"Demo_Legacy_Patch.zip"
            write_patch(patch, {"schema":"vault.patch.v1","engine":"vault","project":"Demo","patchId":"DEMO-LEGACY-001","files":[]})
            with env(VAULT_SETTINGS_PATH=str(settings), VAULT_STORAGE_ROOT=str(base/"Library"), VAULT_ARTIFACT_CENTRAL_ROOT=str(base/"Artifacts"), VAULT_INTAKE_PATHS=str(downloads)):
                save_settings({"vaultHome":str(base/"Vault"),"security":{"legacyPatchPolicy":"review"}})
                result=scan_intake(extra_roots=(project,),force_stable=True,remove_source=True)
            self.assertEqual(result["errors"],[],result)
            self.assertEqual(result["ingested"][0]["state"],"QUEUED",result)

    def test_trusted_project_root_never_archives_normal_source_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); project=base/"VaultLikeProject"; project.mkdir(); downloads=base/"Downloads"; downloads.mkdir(); settings=base/"settings.json"
            manifest_file=project/"VAULT_PACKAGE_MANIFEST.json"
            manifest_file.write_text(json.dumps({"schema":"vault.package.manifest.v1","files":[]}),encoding="utf-8")
            (project/"project.control.json").write_text(json.dumps({"project":{"id":"vault-like","name":"VaultLikeProject"},"commands":[]}),encoding="utf-8")
            with env(VAULT_SETTINGS_PATH=str(settings),VAULT_STORAGE_ROOT=str(base/"Library"),VAULT_ARTIFACT_CENTRAL_ROOT=str(base/"Artifacts"),VAULT_INTAKE_PATHS=str(downloads)):
                save_settings({"vaultHome":str(base/"Vault"),"artifactCentralRoot":str(base/"Artifacts")})
                result=scan_intake(extra_roots=(project,),force_stable=True,remove_source=True)
            self.assertTrue(manifest_file.is_file(), result)
            self.assertEqual(result["artifacts"],[],result)

    def test_artifact_central_creates_project_category_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); source=base/"Demo_DebugBundle_001.zip"; source.write_bytes(b"debug")
            with env(VAULT_ARTIFACT_CENTRAL_ROOT=str(base/"ArtifactCentral")):
                receipt=archive_file(source,"demo",move=True)
            target=Path(receipt["artifactPath"])
            self.assertTrue(target.is_file()); self.assertEqual(receipt["category"],"debug-bundles"); self.assertFalse(source.exists())
            self.assertTrue((target.parent/"artifact.receipt.json").is_file())

    def test_ide_path_access_is_project_confined(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"Project"; root.mkdir(); inside=root/"x.py"; inside.write_text("print(1)",encoding="utf-8")
            self.assertEqual(confined(root,"x.py"),inside.resolve())
            with self.assertRaises(PermissionError): confined(root,"../outside.txt")

    def test_tooling_audit_discovers_root_launcher_blender_and_declared_commands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"Demo"; root.mkdir(); (root/"PROJECT_CONTROL_CENTER.cmd").write_text("@echo off\n",encoding="utf-8")
            b=root/"tools"/"blender"; b.mkdir(parents=True); (b/"export_asset.py").write_text("print('x')\n",encoding="utf-8")
            (root/"project.control.json").write_text(json.dumps({"project":{"id":"demo"},"commands":[{"key":"gate.full","label":"Full","program":"python","args":[]}]}),encoding="utf-8")
            report=audit_project(root)
            paths={x["path"] for x in report["scripts"]}
            self.assertIn("PROJECT_CONTROL_CENTER.cmd",paths); self.assertIn("tools/blender/export_asset.py",paths)
            self.assertEqual(report["commandCount"],1); self.assertEqual(len(report["blenderScripts"]),1)

    def test_tray_menu_exposes_workflow_surfaces(self) -> None:
        keys={x.key for x in DEFAULT_MENU}
        for required in {"open","projects","workspace","full-gate","apply-updates","source-control","forgejo","ide","cortex","settings","exit"}:
            self.assertIn(required,keys)

    def test_open_source_component_registry_is_license_explicit(self) -> None:
        rows=component_inventory()["components"]
        names={row["key"]:row for row in rows}
        self.assertEqual(names["monaco"]["license"],"MIT")
        self.assertEqual(names["pywebview"]["license"],"BSD-3-Clause")
        self.assertEqual(names["tree-sitter"]["license"],"MIT")
        self.assertIn("MIT",names["ripgrep"]["license"])


if __name__ == "__main__":
    unittest.main()
