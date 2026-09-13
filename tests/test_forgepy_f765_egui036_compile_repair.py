import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ForgePYF765Egui036CompileRepairTests(unittest.TestCase):
    def text(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_candidate_identity_is_f765(self):
        import sys
        sys.path.insert(0, str(ROOT / "app"))
        from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
        self.assertEqual(DISPLAY_BUILD, "FORGEPY-F777")
        self.assertEqual(DISPLAY_VERSION, "0.5.0-candidate.777")

    def test_egui_036_theme_api_is_used(self):
        theme = self.text("native/forge-rs/src/gui/theme.rs")
        self.assertIn("Theme::Dark", theme)
        self.assertIn("ctx.set_theme(Theme::Dark)", theme)
        self.assertIn("ctx.style_of(Theme::Dark)", theme)
        self.assertIn("ctx.set_style_of(Theme::Dark, style)", theme)
        self.assertNotIn("ctx.style()", theme)
        self.assertNotIn("ctx.set_style(style)", theme)

    def test_native_identity_tracks_compile_repair(self):
        identity = self.text("native/forge-rs/src/identity.rs")
        self.assertIn('NATIVE_VERSION: &str = "0.5.0-shadow"', identity)
        self.assertIn('NATIVE_BUILD: &str = "FORGE-NATIVE-GUI-WAVE2-0.5.0-F776"', identity)


if __name__ == "__main__":
    unittest.main()
