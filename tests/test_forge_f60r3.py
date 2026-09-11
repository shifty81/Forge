from __future__ import annotations
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ForgeF60R3Tests(unittest.TestCase):
    def test_no_duplicate_header_health_monitor(self):
        text=(ROOT/'app'/'ForgeGui.py').read_text(encoding='utf-8')
        self.assertNotIn('self.header_health_host =', text)
        self.assertNotIn('self._build_header_health_rail(self.header_health_rail)', text)
        self.assertIn('self._build_project_health_gauge(self.health_host)', text)

    def test_tray_declares_pointer_sized_winapi_signatures(self):
        text=(ROOT/'app'/'VaultTray.py').read_text(encoding='utf-8')
        self.assertIn('DefWindowProcW.argtypes', text)
        self.assertIn('DefWindowProcW.restype = LRESULT', text)
        self.assertIn('CreateWindowExW.restype = wintypes.HWND', text)
        self.assertIn('WINFUNCTYPE(LRESULT', text)
        self.assertIn('class ForgeTray:', text)

    def test_forge_is_product_authority(self):
        import sys
        sys.path.insert(0, str(ROOT/'app'))
        from ForgeVersion import VERSION, BUILD, PRODUCT
        self.assertEqual(PRODUCT, 'ForgePY')
        self.assertEqual(VERSION, "0.4.389-F60R389")
        self.assertEqual(BUILD, "FORGEPY-F60R389")

if __name__=='__main__': unittest.main()
