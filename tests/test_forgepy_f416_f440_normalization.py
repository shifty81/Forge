from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import ForgeF440Normalization as norm


class ForgePYF416F440NormalizationTests(unittest.TestCase):
    def test_category_contract(self):
        self.assertEqual(norm._category_for("assets.blender.export", "Blender Export"), "Content & Assets")
        self.assertEqual(norm._category_for("world.pcg.validate", "Worldgen"), "World & Data")
        self.assertEqual(norm._category_for("package.release", "Release"), "Packaging & Release")
        self.assertEqual(norm._category_for("git.push", "Push"), "Advanced")

    def test_update_policy_dependencies_and_supersedence(self):
        waiting = {
            "state": "AVAILABLE", "patch_id": "PATCH-B",
            "manifest": {"requires": ["PATCH-A"]},
        }
        bucket, reason = norm._policy_state(waiting, [waiting])
        self.assertEqual(bucket, "NEEDS ATTENTION")
        self.assertIn("PATCH-A", reason)

        applied = {"state": "APPLIED", "patch_id": "PATCH-A", "manifest": {}}
        bucket, _reason = norm._policy_state(waiting, [applied, waiting])
        self.assertEqual(bucket, "READY")

        old = {"state": "AVAILABLE", "patch_id": "PATCH-OLD", "manifest": {}}
        new = {"state": "AVAILABLE", "patch_id": "PATCH-NEW", "manifest": {"supersedes": ["PATCH-OLD"]}}
        bucket, reason = norm._policy_state(old, [old, new])
        self.assertEqual(bucket, "HISTORY")
        self.assertIn("PATCH-NEW", reason)

    def test_recovery_ref_is_private_forgepy_ref(self):
        self.assertEqual(norm.recovery_ref(Path("."), "feature/worldgen"), "refs/forgepy/recovery/feature/worldgen")

    def test_recovery_ref_lifecycle(self):
        git = "git"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run([git, "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([git, "config", "user.email", "forgepy@example.invalid"], cwd=root, check=True)
            subprocess.run([git, "config", "user.name", "ForgePY Test"], cwd=root, check=True)
            (root / "a.txt").write_text("one\n", encoding="utf-8")
            subprocess.run([git, "add", "a.txt"], cwd=root, check=True)
            subprocess.run([git, "commit", "-m", "one"], cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ref = norm.ensure_recovery_ref(root, "main")
            self.assertEqual(ref, "refs/forgepy/recovery/main")
            first = norm.recovery_sha(root, "main")
            self.assertTrue(first)
            (root / "a.txt").write_text("two\n", encoding="utf-8")
            subprocess.run([git, "add", "a.txt"], cwd=root, check=True)
            subprocess.run([git, "commit", "-m", "two"], cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(norm.recovery_sha(root, "main"), first)
            norm.advance_recovery(root, "main")
            self.assertNotEqual(norm.recovery_sha(root, "main"), first)

    def test_simplified_ux_installs_normalization(self):
        source = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("from ForgeF440Normalization import install_normalization", source)
        self.assertIn("install_normalization(cls)", source)


    def test_provider_protocol_v1(self):
        import ForgeProviderProtocol as proto
        cmd = proto.ProviderCommandV1("world.validate", "Validate World", "World & Data", "world.validate")
        data = proto.descriptor("demo", "Demo", [cmd])
        self.assertEqual(proto.compatibility_state(data), "CURRENT")
        self.assertEqual(proto.validate_descriptor(data), [])
        kit = proto.project_reference_files()
        self.assertIn(".forgepy/forgepy-version.lock", kit)

    def test_normalization_has_no_monaco_lane(self):
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertNotIn("Open Monaco Window", source)
        self.assertIn("Native authoritative IDE surface", source)
        self.assertIn("Command Palette", source)
        self.assertIn("Apply + Full Gate", source)

    def test_project_cli_is_integrated_into_project_console(self):
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertIn("def _open_project_cli_console", source)
        self.assertIn("PROJECT CLI ·", source)
        self.assertIn("_console_show_suggestions(force_all=True)", source)
        self.assertNotIn('gui._button(row, "Project CLI", gui._open_cli', source)

    def test_live_console_policy_disables_large_batch_delay(self):
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertIn('"consoleBatchLines": 1', source)
        self.assertIn("def _console_heartbeat", source)
        self.assertIn("waiting for provider output", source)
        self.assertIn("_forge_last_child_output", source)
        self.assertIn("def _universal_apply_heartbeat", source)
        self.assertIn("the requested Full Gate did not start", source)

    def test_project_command_transcript_is_logged_before_process_output(self):
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertIn("def _start_command_live", source)
        self.assertIn('[CLI]', source)
        self.assertIn("_safe_cli_argv", source)

    def test_status_refresh_accepts_f415_tuple_update_counts(self):
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertIn("counts_for_project(", source)
        self.assertIn("isinstance(counts, (tuple, list))", source)
        self.assertIn("counts_for_project legacy contract: (pending, invalid)", source)
        self.assertNotIn('pending = int(counts.get("available", 0) or 0) + int(counts.get("queued", 0) or 0) + int(counts.get("review", 0) or 0)', source)


    def test_failed_gate_debug_falls_back_without_unsupported_provider_popup(self):
        source = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("def _debug_provider_command", source)
        self.assertIn("def _fallback_debug_bundle", source)
        self.assertIn("project provider exposes no debug-bundle command", source)
        self.assertNotIn('gui._start_command("debug-bundle", label="debug-bundle")', source)

    def test_legacy_top_banner_is_hidden_after_normalized_shell_build(self):
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertIn("reclaim the legacy top ForgePY banner entirely", source)
        self.assertIn("child.pack_forget()", source)

    def test_f445_f449_patch_preflight_and_details_contract(self):
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertIn("FORGEPY-NORMALIZATION-F445-F449-CANDIDATE", source)
        self.assertIn("def _preflight_update_item", source)
        self.assertIn("def _update_target_root", source)
        self.assertIn("def _show_update_details", source)
        self.assertIn('"Details"', source)
        self.assertIn("conflictsWith", source)
        self.assertIn("NORMALIZATION_VERSION", source)

    def test_queued_resume_uses_catalog_bound_target(self):
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        start = source.index("def _apply_ready_item")
        end = source.index("def _approve_selected_review", start)
        block = source[start:end]
        self.assertIn("root, preflight = _preflight_update_item", block)
        self.assertIn('_start_universal_project_apply(root, "apply-updates", run_full_after=True)', block)
        self.assertNotIn('_start_universal_project_apply(Path(gui.root_path), "apply-updates", run_full_after=True)', block)

    def test_provider_operations_require_verified_or_certified_tools(self):
        import ForgeProviderProtocol as proto
        self.assertEqual(proto.verified_operation_states(), ("VERIFIED", "CERTIFIED"))
        report = proto.compatibility_report(proto.descriptor("demo", "Demo", [proto.ProviderCommandV1("world.validate", "Validate", "World & Data", "world.validate")]))
        self.assertTrue(report["valid"])
        source = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertIn('state not in {"VERIFIED", "CERTIFIED"}', source)
        self.assertNotIn('state not in {"VERIFIED", "CERTIFIED", "CONFIGURED"}', source)

    def test_source_authority_audit_is_full_gate_preflight(self):
        import ForgeSourceAuthority as authority
        self.assertEqual(authority.SCHEMA, "forgepy.source-authority.v1")
        gate = (ROOT / "tools" / "ForgePYGate.py").read_text(encoding="utf-8")
        self.assertIn("ForgeSourceAuthority.py", gate)
        self.assertIn("_source_authority_check_for_full", gate)


if __name__ == "__main__":
    unittest.main()
