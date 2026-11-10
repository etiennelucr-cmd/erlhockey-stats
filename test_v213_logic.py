"""Tests unitaires sans accès à NHL/Supabase (nécessitent requirements.txt)."""
import unittest
from datetime import datetime, timezone, timedelta
from auto_picks_v21 import upcoming_games, current_roster_ids


class V213SafetyTests(unittest.TestCase):
    def test_upcoming_ignores_past(self):
        now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
        future = (now + timedelta(hours=2)).isoformat().replace('+00:00', 'Z')
        past = (now - timedelta(hours=2)).isoformat().replace('+00:00', 'Z')
        def fetch(day):
            return {'games': [{'id': 1, 'startTimeUTC': future},
                              {'id': 2, 'startTimeUTC': past}]}
        self.assertEqual(set(upcoming_games(now, fetch)), {1})

    def test_roster_fails_closed_when_missing(self):
        with self.assertRaises(ValueError):
            current_roster_ids({'TOR'}, roster_fetch=lambda team: {})

    def test_rosters_are_separated_by_team(self):
        def fetch(team):
            return {'forwards': [{'id': 11 if team == 'TOR' else 22}],
                    'defensemen': [], 'goalies': []}
        rosters = current_roster_ids({'TOR', 'COL'}, roster_fetch=fetch)
        self.assertNotIn('11', rosters['COL'])

if __name__ == '__main__':
    unittest.main()
