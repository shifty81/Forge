from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "tools" / "rust" / "ForgeNativeUpdateBridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("forge_native_update_bridge", BRIDGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load ForgeNativeUpdateBridge")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ForgeNativeSelfUpdateFoundationTests(unittest.TestCase):
    def text(self, rel: str) -> str:
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_rust_update_module_is_registered(self) -> None:
        lib = self.text("native/forge-rs/src/lib.rs")
        update = self.text("native/forge-rs/src/update.rs")
        self.assertIn("pub mod update;", lib)
        self.assertIn("pub enum InstallMode", update)
        self.assertIn("Portable", update)
        self.assertIn("Installed", update)
        self.assertIn("Development", update)
        self.assertIn("write_promotion_helper", update)
        self.assertIn("arm_promotion", update)
        self.assertIn(".forge-portable", update)
        self.assertIn(".forgepy-portable", update)

    def test_native_cli_exposes_update_certification_surface(self) -> None:
        main = self.text("native/forge-rs/src/main.rs")
        for token in (
            '"--update-status-json"',
            '"--build-native-update"',
            '"--stage-native-update"',
            '"--stage-and-arm-native-update"',
        ):
            self.assertIn(token, main)

    def test_parity_records_self_update_without_claiming_takeover(self) -> None:
        matrix = json.loads(self.text("native/forge-rs/parity/matrix.json"))
        self.assertEqual(matrix["candidate"], "FORGEPY-F797")
        self.assertFalse(matrix["takeoverReady"])
        rows = {row["capability"]: row for row in matrix["rows"]}
        self.assertEqual(rows["native-self-update"]["state"], "DIFFERENT")
        self.assertIn("SHADOW bridge", rows["native-self-update"]["note"])

    def test_bridge_build_inspect_and_stage_roundtrip(self) -> None:
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "image"
            image.mkdir()
            (image / "ForgeNative.exe").write_bytes(b"native-exe-v2")
            (image / "support").mkdir()
            (image / "support" / "runtime.dll").write_bytes(b"runtime-v2")
            (image / "Data").mkdir()
            (image / "Data" / "settings.json").write_text("should-not-ship", encoding="utf-8")
            (image / ".forge-portable").write_text("local-marker\n", encoding="utf-8")

            bundle = root / "ForgeNative-test.forgeupdate"
            result = bridge.build_bundle(
                image,
                bundle,
                "ForgeNative.exe",
                "0.5.0-shadow",
                "FORGE-NATIVE-TEST",
            )
            self.assertTrue(bundle.is_file())
            self.assertEqual(result["fileCount"], 2)

            with zipfile.ZipFile(bundle) as archive:
                names = set(archive.namelist())
                self.assertIn("FORGE_NATIVE_UPDATE_MANIFEST.json", names)
                self.assertIn("image/ForgeNative.exe", names)
                self.assertIn("image/support/runtime.dll", names)
                self.assertNotIn("image/Data/settings.json", names)
                self.assertNotIn("image/.forge-portable", names)

            inspected = bridge.inspect_bundle(bundle, "ForgeNative.exe")
            self.assertEqual(inspected["entrypoint"], "ForgeNative.exe")
            self.assertEqual(len(inspected["files"]), 2)

            current = root / "PortableForge"
            current.mkdir()
            (current / "ForgeNative.exe").write_bytes(b"native-exe-v1")
            (current / ".forge-portable").write_text("portable\n", encoding="utf-8")
            (current / "Data").mkdir()
            (current / "Data" / "settings.json").write_text("{}", encoding="utf-8")
            maintenance = root / ".PortableForge.ForgeMaintenance"
            plan = bridge.stage_bundle(
                bundle,
                current,
                maintenance,
                "portable",
                "ForgeNative.exe",
            )
            staged = Path(plan["stagedRoot"])
            self.assertTrue((staged / "ForgeNative.exe").is_file())
            self.assertTrue((staged / "support" / "runtime.dll").is_file())
            self.assertFalse((staged / "Data").exists())
            self.assertFalse(str(staged).casefold().startswith(str(current).casefold()))
            self.assertTrue(Path(plan["planJson"]).is_file())

    def test_bridge_rejects_traversal_and_unexpected_payload(self) -> None:
        bridge = load_bridge()
        with self.assertRaisesRegex(RuntimeError, "unsafe native update path"):
            bridge.safe_relative("../escape.dll")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root / "bad.forgeupdate"
            manifest = {
                "schema": bridge.MANIFEST_SCHEMA,
                "applicationVersion": "x",
                "applicationBuild": "y",
                "entrypoint": "ForgeNative.exe",
                "files": [
                    {
                        "path": "ForgeNative.exe",
                        "bytes": 1,
                        "sha256": bridge.hashlib.sha256(b"x").hexdigest(),
                    }
                ],
            }
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr(bridge.MANIFEST_NAME, json.dumps(manifest))
                archive.writestr("image/ForgeNative.exe", b"x")
                archive.writestr("image/not-governed.txt", b"surprise")
            with self.assertRaisesRegex(RuntimeError, "unexpected files"):
                bridge.inspect_bundle(bundle, "ForgeNative.exe")

    def test_bridge_rejects_maintenance_inside_live_root(self) -> None:
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as td:
            current = Path(td) / "Forge"
            current.mkdir()
            with self.assertRaisesRegex(RuntimeError, "outside the live application root"):
                bridge.ensure_outside(current / "Updates", current)


if __name__ == "__main__":
    unittest.main()
