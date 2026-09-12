from __future__ import annotations
import hashlib, json, sys, tempfile, unittest, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path: sys.path.insert(0, str(APP))
import VaultPatchEngine
from ForgePYVersion import VERSION, BUILD

def digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()

class ForgePYF60R24Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION, "0.4.390-F60R390")
        self.assertEqual(BUILD, "FORGEPY-F60R390")
    def _make_patch(self, td: Path, rel: str, before: bytes, after: bytes) -> Path:
        patch = td / "test.patch"
        manifest = {"schema":"forge.patch.v1","engine":"forge-universal","project":"forgepy","patchId":"TEST-R24","files":[{"path":rel,"operation":"write","preSha256":digest(before),"sha256":digest(after),"bytes":len(after)}]}
        with zipfile.ZipFile(patch,"w",zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("PATCH_MANIFEST.json", json.dumps(manifest))
            zf.writestr("payload/"+rel, after)
        return patch
    def test_crlf_materialization_matches_lf_preimage(self):
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); root=td/"ForgePY"; target=root/"app"/"sample.py"; target.parent.mkdir(parents=True)
            before=b"alpha = 1\nbeta = 2\n"; target.write_bytes(before.replace(b"\n",b"\r\n"))
            patch=self._make_patch(td,"app/sample.py",before,b"alpha = 2\nbeta = 2\n")
            self.assertEqual(len(VaultPatchEngine.validate_transport(patch,root)["files"]),1)
    def test_already_target_is_satisfied(self):
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); root=td/"ForgePY"; target=root/"app"/"sample.py"; target.parent.mkdir(parents=True)
            before=b"value = 1\n"; after=b"value = 2\n"; target.write_bytes(after)
            patch=self._make_patch(td,"app/sample.py",before,after)
            self.assertEqual(len(VaultPatchEngine.validate_transport(patch,root)["files"]),1)
    def test_binary_mismatch_remains_strict(self):
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); root=td/"ForgePY"; target=root/"assets"/"blob.bin"; target.parent.mkdir(parents=True)
            before=b"\x00\x01\x02"; target.write_bytes(b"\x00\x01\x03")
            patch=self._make_patch(td,"assets/blob.bin",before,b"\x00\x01\x04")
            with self.assertRaises(VaultPatchEngine.PatchError): VaultPatchEngine.validate_transport(patch,root)
