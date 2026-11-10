import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import sys
from types import ModuleType
# The filtering function is pure, while Streamlit and tracker require deployment dependencies.
try:
    import streamlit
except ImportError:
    sys.modules['streamlit'] = ModuleType('streamlit')
try:
    import tracker_v14
except ImportError:
    fake = ModuleType('tracker_v14')
    fake.follow = lambda *a, **k: None
    fake.connect = lambda: None
    sys.modules['tracker_v14'] = fake
from nhl_picks_v20 import filter_games_by_period

class TestPeriod(unittest.TestCase):
    def test_periods_and_past(self):
        paris=ZoneInfo('Europe/Paris')
        now=datetime(2026,11,10,11,0,tzinfo=paris)
        rows=[{'kickoff':datetime(2026,11,d,h,tzinfo=paris),'game_id':i}
              for i,(d,h) in enumerate([(10,9),(10,20),(11,2),(11,22),(12,1)])]
        self.assertEqual([r['game_id'] for r in filter_games_by_period(rows,'Ce soir',now)],[1])
        self.assertEqual([r['game_id'] for r in filter_games_by_period(rows,'Demain',now)],[2,3])
        self.assertEqual([r['game_id'] for r in filter_games_by_period(rows,'Mixte',now)],[1,2,3])
        self.assertEqual(filter_games_by_period(rows,'Other',now),[])
if __name__=='__main__': unittest.main()
