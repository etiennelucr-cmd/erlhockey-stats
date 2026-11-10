import unittest
from auto_picks_v21 import current_roster_ids

class RosterTests(unittest.TestCase):
    def test_team_ids_are_separate(self):
        def fetch(team):
            return {'forwards': [{'id': 10 if team == 'TOR' else 20}], 'defensemen': [], 'goalies': []}
        result = current_roster_ids({'TOR', 'COL'}, roster_fetch=fetch)
        self.assertEqual(result['TOR'], {'10'})
        self.assertNotIn('10', result['COL'])

    def test_missing_roster_fails_closed(self):
        with self.assertRaises(ValueError):
            current_roster_ids({'TOR'}, roster_fetch=lambda _: {})

    def test_empty_roster_fails_closed(self):
        with self.assertRaises(ValueError):
            current_roster_ids({'TOR'}, roster_fetch=lambda _: {'forwards': []})

if __name__ == '__main__':
    unittest.main()
