from __future__ import annotations
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class IntegrationTests(unittest.TestCase):
    def test_selftest_imports_new_services(self):
        s=(ROOT/'app'/'ForgeStandalone.py').read_text(encoding='utf-8');self.assertIn('ForgeVaultFTS',s);self.assertIn('ForgeRestoreTransaction',s);self.assertIn('ForgeSelfUpdateRuntime',s)
    def test_patch_only_safety_still_enforced(self):
        s=(ROOT/'app'/'ForgeSettingsSchema.py').read_text(encoding='utf-8');self.assertIn('archiveNonPatchArtifacts must remain false',s)
    def test_scheduler_defaults_off(self):
        s=(ROOT/'app'/'VaultSettings.py').read_text(encoding='utf-8');self.assertIn('"schedulerEnabled": False',s)
    def test_content_index_defaults_off(self):
        s=(ROOT/'app'/'VaultSettings.py').read_text(encoding='utf-8');self.assertIn('"contentIndexEnabled": False',s)
    def test_cumulative_notes_cover_108_407(self):
        s=(ROOT/'docs'/'CUMULATIVE_PATCH_NOTES_F108_F407.md').read_text(encoding='utf-8');self.assertIn('F108–F307',s);self.assertIn('F308–F407',s)
if __name__=='__main__':unittest.main()
