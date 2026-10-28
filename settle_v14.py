"""Settle tracked V14 predictions using final NHL records. Run after NHL collection."""
import os
import re
import logging
import psycopg

LOG=logging.getLogger(__name__)

def evaluate(selection, game, player_rows):
    home,away,hs,as_=game
    if hs is None or as_ is None: return None
    total=int(hs)+int(as_)
    if selection.startswith('Plus de ') or selection.startswith('Moins de '):
        m=re.fullmatch(r'(Plus|Moins) de (\d+[,.]\d+) buts',selection)
        if not m: return 'void'
        line=float(m.group(2).replace(',','.'))
        return 'won' if ((total>line) if m.group(1)=='Plus' else (total<line)) else 'lost'
    # NHL final score includes OT/SO; 60-minute result cannot be inferred from final alone.
    if '(60 min)' in selection:
        return 'void'
    m=re.fullmatch(r'(.+?) — (1\+ point|2\+ points|1\+ but)',selection)
    if not m: return 'void'
    name,market=m.groups()
    matching=[r for r in player_rows if r[0]==name]
    if len(matching)!=1:
        return 'void'  # no confirmed player stats, do not mark an absence as loss
    goals,points=matching[0][1:]
    threshold=2 if market=='2+ points' else 1
    actual=goals if market=='1+ but' else points
    return 'won' if actual>=threshold else 'lost'

def settle(conn):
    rows=conn.execute('''SELECT l.id,l.game_id,l.selection,g.home_team,g.away_team,g.home_score,g.away_score
       FROM tracked_legs l JOIN nhl_games g ON g.game_id=l.game_id
       WHERE l.status='pending' AND g.game_state IN ('OFF','FINAL')''').fetchall()
    for leg_id,gid,selection,home,away,hs,as_ in rows:
        players=conn.execute('SELECT player_name,goals,points FROM nhl_player_games WHERE game_id=%s',(gid,)).fetchall()
        outcome=evaluate(selection,(home,away,hs,as_),players)
        if outcome:
            conn.execute("UPDATE tracked_legs SET status=%s WHERE id=%s AND status='pending'",(outcome,leg_id))
    conn.execute('''UPDATE tracked_combos c SET status = CASE
        WHEN EXISTS (SELECT 1 FROM tracked_legs l WHERE l.combo_id=c.id AND l.status='lost') THEN 'lost'
        WHEN NOT EXISTS (SELECT 1 FROM tracked_legs l WHERE l.combo_id=c.id AND l.status='pending')
             AND NOT EXISTS (SELECT 1 FROM tracked_legs l WHERE l.combo_id=c.id AND l.status='void') THEN 'won'
        WHEN NOT EXISTS (SELECT 1 FROM tracked_legs l WHERE l.combo_id=c.id AND l.status='pending') THEN 'void'
        ELSE 'pending' END WHERE c.status='pending' ''')
    LOG.info('V14 settled %d legs',len(rows))

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    with psycopg.connect(os.environ['SUPABASE_DB_URL']) as conn:
        settle(conn)
