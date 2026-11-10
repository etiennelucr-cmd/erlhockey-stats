from datetime import datetime, timezone
import pandas as pd
from nhl_picks_v20 import candidate_picks, PROFILES

def test_seven_games_each_profile():
    rows=[]
    history=[]
    for game in range(7):
        for player in range(5):
            pid=game*10+player
            rows.append({'player_id':pid,'game_id':game+1,'kickoff':datetime(2027,1,1,tzinfo=timezone.utc),'Match':f'A{game} @ B{game}','Joueur':f'Player {pid}','Équipe':f'A{game}'})
            for n in range(10):
                history.append({'player_id':pid,'rn':n+1,'points':int(n < (10-player*2)),'goals':int(n < (5-player))})
    picks=candidate_picks(rows,pd.DataFrame(history))
    assert all(len(picks[name])==7 for name in PROFILES)
    assert all(len({p['game_id'] for p in picks[name]})==7 for name in PROFILES)
    for game in range(1,8):
        assert len({next(p for p in picks[name] if p['game_id']==game)['player_id'] for name in PROFILES})==5

def test_fallback_when_no_player_in_profile_range():
    row={'player_id':1,'game_id':1,'kickoff':datetime(2027,1,1,tzinfo=timezone.utc),'Match':'A @ B','Joueur':'One','Équipe':'A'}
    history=pd.DataFrame([{'player_id':1,'rn':n+1,'points':1,'goals':0} for n in range(10)])
    result=candidate_picks([row],history)
    assert all(len(result[name])==1 for name in PROFILES)
    assert result['Ultra risqué'][0]['fallback']
