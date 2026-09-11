from __future__ import annotations
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SafetyTests(unittest.TestCase):
    def test_nonpatch_auto_archive_remains_disabled(self):
        src=(ROOT/'app'/'VaultSettings.py').read_text(encoding='utf-8'); self.assertIn('"archiveNonPatchArtifacts": False',src)
    def test_legacy_tray_remains_fail_closed_on_python314(self):
        src=(ROOT/'app'/'VaultTray.py').read_text(encoding='utf-8'); self.assertIn('FORGEPY_ENABLE_LEGACY_NATIVE_TRAY',src)
    def test_startup_surface_teardown_remains(self):
        src=(ROOT/'app'/'ForgeStartup.py').read_text(encoding='utf-8'); self.assertIn('frame.destroy()',src); self.assertIn('root.quit()',src)
    def test_release_does_not_claim_native_exe(self):
        doc=(ROOT/'docs'/'NEXT_100_PASSES_F108_F207.md').read_text(encoding='utf-8'); self.assertIn('not falsely certified as Windows binaries',doc)
if __name__=='__main__':unittest.main()
