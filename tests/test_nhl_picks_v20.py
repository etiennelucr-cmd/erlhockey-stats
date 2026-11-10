from datetime import datetime, timezone
import pandas as pd
from nhl_picks_v20 import candidate_picks, PROFILES

def test_empty():
    assert all(not v for v in candidate_picks([], pd.DataFrame()).values())

def test_classification_and_no_duplicates():
    rows=[{'player_id':1,'game_id':123,'kickoff':datetime(2027,1,1,tzinfo=timezone.utc),'Match':'A @ B','Joueur':'Test','Équipe':'A'}]
    history=pd.DataFrame([{'player_id':1,'rn':i+1,'points':1,'goals':0} for i in range(10)])
    result=candidate_picks(rows,history)
    assert len(result['Prudent'])==1
    assert result['Prudent'][0]['selection']=='Test — 1+ point'
    assert len({(x['game_id'],x['player']) for v in result.values() for x in v})>=1

def test_missing_game_rejected():
    rows=[{'player_id':1,'game_id':None,'kickoff':datetime.now(timezone.utc),'Match':'A @ B','Joueur':'Test','Équipe':'A'}]
    history=pd.DataFrame([{'player_id':1,'rn':i+1,'points':1,'goals':0} for i in range(10)])
    assert all(not x for x in candidate_picks(rows,history).values())
