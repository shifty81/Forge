from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ForgePYVersion import VERSION, BUILD


class F60R415SimplifiedWorkflowTests(unittest.TestCase):
    def test_identity(self) -> None:
        self.assertEqual(VERSION, "0.4.415-F60R415")
        self.assertEqual(BUILD, "FORGEPY-F60R415")

    def test_simplified_ux_declares_native_drop_and_one_click_gate(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("WM_DROPFILES", text)
        self.assertIn("DragAcceptFiles", text)
        self.assertIn('"CHECK FOR UPDATES"', text)
        self.assertIn('"patch-apply", ["--yes"], label="apply-updates"', text)
        self.assertIn('self.gui._start_command("full")', text)

    def test_green_is_automatic_publish_boundary(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn('"commit-push-green"', text)
        self.assertIn("_start_builtin_source", text)
        self.assertIn('"source-commit-push-green"', text)
        self.assertIn("GitHub publication is pending", text)

    def test_source_control_is_two_primary_tabs(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn('("Local Source", "GitHub")', text)
        self.assertIn('"BACKUP SOURCE"', text)
        self.assertIn('"RESTORE SOURCE"', text)
        self.assertIn('"BACKUP TO GITHUB"', text)
        self.assertIn('"RESTORE FROM GITHUB"', text)
        self.assertNotIn('pages = {name: tk.Frame(body, bg="#090b0e") for name in ("Local Source", "GitHub",', text)

    def test_project_tools_require_verified_state(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn('if state != "VERIFIED":', text)
        self.assertIn('text="PROJECT TOOLS"', text)
        self.assertIn("ForgeToolRegistry", text)

    def test_patch_target_is_resolved_globally(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("resolve_patch_target(source)", text)
        self.assertIn('status == "RESOLVED"', text)
        self.assertIn('status == "AMBIGUOUS"', text)
        self.assertNotIn("resolve_patch_target(source, project_hint=gui.root_path)", text)

    def test_cross_project_patch_does_not_change_visible_project(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        start = text.index("def _approve_manual_and_gate")
        end = text.index("def _choose_patch", start)
        block = text[start:end]
        self.assertNotIn("_activate_project", block)
        self.assertIn("without changing the visible workspace", text)
        self.assertIn("_start_universal_project_apply(target_root", text)

    def test_debug_reveal_uses_file_selection_handoff(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("latest_debug_bundle", text)
        self.assertIn("reveal_file", text)
        self.assertIn("/select,", text)

    def test_compatibility_snapshot_is_vault_side_read_only_reference(self) -> None:
        text = (APP / "ForgeCompatibilitySnapshot.py").read_text(encoding="utf-8")
        self.assertIn('"read-only-vault-reference"', text)
        self.assertIn("ensure_artifact_project_tree", text)
        self.assertNotIn("project_root / '.forgepy'", text)

    def test_worker_callbacks_are_marshaled_to_main_thread(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("_forge_main_actions", text)
        self.assertIn("_dispatch_main", text)
        self.assertIn("_drain_main_actions", text)
        self.assertNotIn("gui.window.after(0, lambda: _present_patch_resolution", text)

    def test_quickbar_and_statusbar_replace_duplicate_shell_rows(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("def _build_simplified_quick_actions", text)
        self.assertIn("def _build_simplified_status_bar", text)
        self.assertIn("cls._build_global_quick_actions = build_quick_actions", text)
        self.assertIn("cls._build_global_statusbar = build_statusbar", text)
        self.assertNotIn("_install_quickbar(self)", text)
        self.assertNotIn("_install_status_bar(self)", text)

    def test_legacy_commit_push_actions_are_removed_from_daily_surface(self) -> None:
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn('("COMMIT + PUSH", "COMMIT + PUSH GREEN")', text)


if __name__ == "__main__":
    unittest.main()
