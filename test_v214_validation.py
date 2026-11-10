"""Unit tests for NHL roster ownership and safe date selection."""
import unittest
from datetime import datetime, timezone, timedelta
from auto_picks_v21 import current_roster_ids, upcoming_games

class ValidationTests(unittest.TestCase):
    def test_transfer_current_roster_is_authoritative(self):
        def fetch(team):
            return {'forwards': [{'id': 123}] if team == 'COL' else [{'id': 456}], 'defensemen': [], 'goalies': []}
        rosters = current_roster_ids({'COL','TOR'}, roster_fetch=fetch)
        owner = {pid: team for team, members in rosters.items() for pid in members}
        self.assertEqual(owner['123'], 'COL')
        self.assertNotEqual(owner['123'], 'TOR')

    def test_roster_unavailable_fails_closed(self):
        with self.assertRaises(ValueError):
            current_roster_ids({'TOR'}, roster_fetch=lambda team: {})

    def test_past_match_not_selected(self):
        now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
        start = (now - timedelta(hours=1)).isoformat().replace('+00:00','Z')
        self.assertFalse(upcoming_games(now, lambda day: {'games':[{'id':1,'startTimeUTC':start}]}))

if __name__ == '__main__':
    unittest.main()
