from __future__ import annotations
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'app'
if str(APP) not in sys.path: sys.path.insert(0,str(APP))
from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
from ForgePackagePolicy import classification

class ForgePYF777UpdateStateHardeningTests(unittest.TestCase):
    def test_candidate_identity(self):
        self.assertEqual(DISPLAY_BUILD,'FORGEPY-F777')
        self.assertEqual(DISPLAY_VERSION,'0.5.0-candidate.777')
    def test_runtime_generated_cargo_lock_never_breaks_gate(self):
        self.assertEqual(classification('native/forge-rs/Cargo.lock'),'runtime-transient')
        text=(ROOT/'tests/test_forgepy_f755_f764_native_gui_wave.py').read_text(encoding='utf-8')
        self.assertNotIn('assertFalse((ROOT / "native/forge-rs/Cargo.lock").exists())',text)
    def test_fallback_debug_bundle_imports_required_stdlib(self):
        text=(ROOT/'app/ForgeSimplifiedUX.py').read_text(encoding='utf-8')
        for name in ('import re','import shutil','import zipfile'):
            self.assertIn(name,text)
    def test_download_scan_is_update_state_aware(self):
        text=(ROOT/'app/ForgeGui.py').read_text(encoding='utf-8')
        self.assertIn('Update In Progress',text)
        self.assertIn('Update Applied — Restart Pending',text)
        self.assertIn('Approved Update Queued',text)
        self.assertIn('Downloads scan skipped while',text)

if __name__=='__main__': unittest.main()
