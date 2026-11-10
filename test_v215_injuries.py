"""Offline regression checks for V21.5 injury filtering."""
import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from auto_picks_v21 import injury_eligible, injury_snapshot
from availability_v17 import _norm

class InjuryTests(unittest.TestCase):
    def test_injury_matches_initial_and_team(self):
        reports = {(_norm('Jared Spurgeon'), _norm('MIN')): {'status': 'IR'}}
        self.assertFalse(injury_eligible('J. Spurgeon', 'MIN', reports))
        self.assertTrue(injury_eligible('J. Spurgeon', 'TOR', reports))
    def test_stale_snapshot_fails_closed(self):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (datetime.now(timezone.utc)-timedelta(hours=30), 12)
        with self.assertRaisesRegex(RuntimeError, 'Generation suspendue'):
            injury_snapshot(conn, datetime.now(timezone.utc))
    def test_recent_snapshot(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (datetime.now(timezone.utc)-timedelta(minutes=5), 1)
        cursor.fetchall.return_value = [('Anthony Mantha','NJD','Out','Neck')]
        data = injury_snapshot(conn, datetime.now(timezone.utc))
        self.assertFalse(injury_eligible('A. Mantha','NJD',data))

if __name__ == '__main__': unittest.main()
