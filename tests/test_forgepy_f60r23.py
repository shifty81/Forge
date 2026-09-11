from __future__ import annotations

import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import VaultDriveIndex
from ForgePYVersion import VERSION, BUILD


class ForgePYF60R23Tests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(VERSION, "0.4.389-F60R389")
        self.assertEqual(BUILD, "FORGEPY-F60R389")

    def test_f60r17_drive_catalog_forward_migrates_before_family_index(self):
        with tempfile.TemporaryDirectory() as td:
            db_file = Path(td) / "drive_index.db"
            db = sqlite3.connect(db_file)
            db.executescript("""
                CREATE TABLE projects(
                    root TEXT PRIMARY KEY,
                    scan_root TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    commands INTEGER NOT NULL,
                    markers_json TEXT NOT NULL,
                    parent_root TEXT NOT NULL,
                    last_seen_utc TEXT NOT NULL
                );
                INSERT INTO projects(root,scan_root,name,kind,provider,commands,markers_json,parent_root,last_seen_utc)
                VALUES('C:/Example','D:/','Example','project','legacy',0,'{}','','2026-09-10T00:00:00Z');
            """)
            db.commit()
            db.close()

            old = VaultDriveIndex.db_path
            VaultDriveIndex.db_path = lambda: db_file
            try:
                migrated = VaultDriveIndex._connect()
                try:
                    pcols = {r[1] for r in migrated.execute("PRAGMA table_info(projects)").fetchall()}
                    self.assertIn("family_hint", pcols)
                    self.assertIn("strength", pcols)
                    indexes = {r[1] for r in migrated.execute("PRAGMA index_list(projects)").fetchall()}
                    self.assertIn("idx_projects_family", indexes)
                    row = migrated.execute("SELECT root,family_hint,strength FROM projects").fetchone()
                    self.assertEqual(row[0], "C:/Example")
                finally:
                    migrated.close()
            finally:
                VaultDriveIndex.db_path = old

    def test_empty_legacy_catalog_can_open_latest_summary(self):
        with tempfile.TemporaryDirectory() as td:
            db_file = Path(td) / "drive_index.db"
            db = sqlite3.connect(db_file)
            db.executescript("""
                CREATE TABLE projects(
                    root TEXT PRIMARY KEY,
                    scan_root TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    commands INTEGER NOT NULL,
                    markers_json TEXT NOT NULL,
                    parent_root TEXT NOT NULL,
                    last_seen_utc TEXT NOT NULL
                );
            """)
            db.close()
            old = VaultDriveIndex.db_path
            VaultDriveIndex.db_path = lambda: db_file
            try:
                self.assertEqual(VaultDriveIndex.latest_summary(), {})
            finally:
                VaultDriveIndex.db_path = old


if __name__ == "__main__":
    unittest.main()
