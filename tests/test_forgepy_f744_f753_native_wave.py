from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class ForgePYF744F753NativeWaveTests(unittest.TestCase):
    def test_f744_green_wrapper_preserves_generation_signature(self):
        text = (APP / "ForgeF440Normalization.py").read_text(encoding="utf-8")
        self.assertIn("def wrapped_after_green(gui: Any, *args: Any, **kwargs: Any)", text)
        self.assertIn("_after_green_wrap(original_green, gui, *args, **kwargs)", text)
        self.assertIn("original(gui, *args, **kwargs)", text)

    def test_f744_wrapper_runtime_forwards_generation_keyword(self):
        import ForgeF440Normalization as normalization
        import ForgeSimplifiedUX as ux

        old_after = ux._after_green
        old_mark = getattr(ux, "_forge_f440_wrapped", False)
        seen = []

        class Window:
            def after(self, *_args, **_kwargs):
                return None

        class Gui:
            root_path = ROOT
            window = Window()

        def receiver(_gui, *, generation=None):
            seen.append(generation)

        try:
            ux._after_green = receiver
            ux._forge_f440_wrapped = False
            normalization._install_callback_registry_bridge()
            ux._after_green(Gui(), generation=77)
            self.assertEqual(seen, [77])
        finally:
            ux._after_green = old_after
            ux._forge_f440_wrapped = old_mark

    def test_f745_green_publication_is_generation_deduped_and_receipted(self):
        text = (APP / "ForgeSimplifiedUX.py").read_text(encoding="utf-8")
        self.assertIn("forgepy.green-publication.v1", text)
        self.assertIn("_forge_green_publish_started_generation", text)
        self.assertIn("_forge_green_publish_completed_generation", text)
        self.assertIn('phase="starting"', text)
        self.assertIn('phase="completed" if int(rc) == 0 else "pending"', text)

    def test_f746_sqlite_exception_paths_close_connections(self):
        text = (APP / "PCCVaultCatalog.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("db: sqlite3.Connection | None = None"), 3)
        self.assertGreaterEqual(text.count("if db is not None:\n            db.close()"), 3)

    def test_f747_native_event_protocol_is_versioned_and_fail_closed(self):
        text = (ROOT / "native/forge-rs/src/protocol.rs").read_text(encoding="utf-8")
        self.assertIn('PROTOCOL_SCHEMA: &str = "forge.native.events.v1"', text)
        self.assertIn("NativeRequest::Unknown", text)
        self.assertIn("to_json_line", text)

    def test_f748_native_process_host_streams_and_stops_tree(self):
        text = (ROOT / "native/forge-rs/src/process_host.rs").read_text(encoding="utf-8")
        self.assertIn("run_streamed", text)
        self.assertIn("try_wait", text)
        self.assertIn("taskkill", text)
        self.assertIn("/T", text)
        self.assertIn("cancellation.requested()", text)

    def test_f749_native_single_flight_jobs_match_forge_semantics(self):
        text = (ROOT / "native/forge-rs/src/jobs.rs").read_text(encoding="utf-8")
        self.assertIn("SingleFlightJobs", text)
        self.assertIn("start_next", text)
        self.assertIn("cancel_active", text)
        self.assertIn("finish_active", text)

    def test_f750_native_project_and_settings_probes_are_bounded(self):
        project = (ROOT / "native/forge-rs/src/project.rs").read_text(encoding="utf-8")
        settings = (ROOT / "native/forge-rs/src/settings.rs").read_text(encoding="utf-8")
        self.assertIn("icon_candidates", project)
        self.assertNotIn("read_dir", project)
        self.assertIn("VAULT_STORAGE_ROOT", settings)
        self.assertIn("project_registry.json", settings)

    def test_f751_native_journal_has_checkpoint_and_rollback(self):
        text = (ROOT / "native/forge-rs/src/journal.rs").read_text(encoding="utf-8")
        self.assertIn("FileJournal", text)
        self.assertIn("checkpoint", text)
        self.assertIn("rollback", text)
        self.assertIn("paths.confined", text)

    def test_f752_native_stdio_and_atomic_evidence_are_exposed(self):
        main = (ROOT / "native/forge-rs/src/main.rs").read_text(encoding="utf-8")
        evidence = (ROOT / "native/forge-rs/src/evidence.rs").read_text(encoding="utf-8")
        lane = (ROOT / "tools/rust/ForgeRustLane.py").read_text(encoding="utf-8")
        self.assertIn("--serve-stdio", main)
        self.assertIn("--write-evidence", main)
        self.assertIn("fs::rename(tmp, path)", evidence)
        self.assertIn('action == "evidence"', lane)

    def test_f753_native_shell_model_tracks_primary_surfaces_and_project_branding(self):
        shell = (ROOT / "native/forge-rs/src/shell.rs").read_text(encoding="utf-8")
        gui = (APP / "ForgeGui.py").read_text(encoding="utf-8")
        self.assertIn('label: "Vault"', shell)
        self.assertIn('label: "Project"', shell)
        self.assertIn('label: "Workspace"', shell)
        self.assertIn('label: "Settings"', shell)
        self.assertIn("project_icon", shell)
        self.assertIn('"Evidence"', gui)
        self.assertIn('"Shell Model"', gui)

    def test_candidate_and_native_builds_advance_to_f753(self):
        from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
        self.assertEqual(DISPLAY_VERSION, "0.5.0-candidate.797")
        self.assertEqual(DISPLAY_BUILD, "FORGEPY-F797")
        identity = (ROOT / "native/forge-rs/src/identity.rs").read_text(encoding="utf-8")
        self.assertIn("FORGE-NATIVE-PCC-ASSET-BRIDGE-0.7.0-F797", identity)

    def test_project_contract_and_parity_state_are_f753_and_fail_closed(self):
        contract = json.loads((ROOT / "project.control.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["project"]["candidateBuild"], "FORGEPY-F797")
        keys = {row.get("key") for row in contract.get("commands", []) if isinstance(row, dict)}
        self.assertTrue({"audit.rust-evidence", "audit.rust-shell"}.issubset(keys))
        matrix = json.loads((ROOT / "native/forge-rs/parity/matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["candidate"], "FORGEPY-F797")
        self.assertFalse(matrix["takeoverReady"])
        states = {row["state"] for row in matrix["rows"]}
        self.assertIn("MISSING", states)
        self.assertIn("DIFFERENT", states)

    def test_rust_library_exports_wave_modules(self):
        lib = (ROOT / "native/forge-rs/src/lib.rs").read_text(encoding="utf-8")
        for name in ("protocol", "process_host", "jobs", "settings", "project", "journal", "shell", "evidence"):
            self.assertIn(f"pub mod {name};", lib)


if __name__ == "__main__":
    unittest.main()
