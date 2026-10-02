import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from lottery_sim.history_db import SCHEMA, init_history_db, load_dashboard_config


class UpgradeCompatibilityTests(unittest.TestCase):
    def test_old_database_is_backed_up_before_additive_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'history.sqlite3'
            with closing(sqlite3.connect(db)) as conn, conn:
                for statement in SCHEMA:
                    conn.execute(statement)
                conn.execute("INSERT INTO dashboard_config VALUES ('llm_model', 'legacy-model')")
                conn.execute("INSERT INTO recommendation_records VALUES ('pl5','2026264','legacy',1,'2026-10-01','旧策略','00834','pending','','',2,0)")
            init_history_db(db)
            backup = db.with_name(db.name + '.pre-1.2.bak')
            self.assertTrue(backup.exists())
            with closing(sqlite3.connect(backup)) as conn:
                self.assertEqual(conn.execute('SELECT numbers FROM recommendation_records').fetchone()[0], '00834')
                self.assertNotIn('payout_basis', {r[1] for r in conn.execute('PRAGMA table_info(recommendation_records)')})
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute('SELECT numbers,payout_basis FROM recommendation_records').fetchone(), ('00834', 'estimated'))
            self.assertEqual(load_dashboard_config(db)['llm_model'], 'legacy-model')
            before = backup.read_bytes()
            init_history_db(db)
            self.assertEqual(backup.read_bytes(), before)

    def test_new_database_does_not_need_migration_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'new.sqlite3'
            init_history_db(db)
            self.assertFalse(db.with_name(db.name + '.pre-1.2.bak').exists())
