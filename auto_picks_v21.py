"""Immutable daily automatic picks, separated from user-followed picks."""
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import psycopg
import requests
from nhl_picks_v20 import candidate_picks, PROFILES

PARIS = ZoneInfo('Europe/Paris')
PREFIX = 'Auto V21 | '


def upcoming_games(now, fetch):
    """Upcoming NHL fixtures on Paris today/tomorrow, fetched for adjacent NHL dates."""
    dates = [(now.astimezone(PARIS).date() + timedelta(days=d)).isoformat() for d in (-1,0,1,2)]
    games = {}
    for day in dates:
        for g in fetch(day).get('games', []):
            try:
                kickoff = datetime.fromisoformat(g['startTimeUTC'].replace('Z', '+00:00'))
                local_day = kickoff.astimezone(PARIS).date()
                if now < kickoff and local_day in {now.astimezone(PARIS).date(), now.astimezone(PARIS).date()+timedelta(days=1)}:
                    games[int(g['id'])] = (g, kickoff)
            except (KeyError, ValueError, TypeError):
                continue
    return games


def generate(conn, now=None, fetch=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    if fetch is None:
        session = requests.Session()
        def fetch(day):
            response = session.get(f'https://api-web.nhle.com/v1/score/{day}', timeout=25)
            response.raise_for_status()
            return response.json()
    games = upcoming_games(now, fetch)
    if not games:
        return 0
    teams = {team.get('abbrev') for g, _ in games.values() for team in (g.get('homeTeam', {}), g.get('awayTeam', {}))}
    teams.discard(None)
    # Only finalized historical rows strictly before generation time: no look-ahead.
    roster = pd.read_sql_query('''SELECT DISTINCT ON (p.player_id) p.player_id,p.player_name,p.team
        FROM nhl_player_games p JOIN nhl_games g ON g.game_id=p.game_id
        WHERE g.game_state IN ('OFF','FINAL') AND g.start_time_utc < %(cutoff)s
          AND p.team = ANY(%(teams)s)
        ORDER BY p.player_id,p.game_date DESC,p.game_id DESC''', conn,
        params={'cutoff':now,'teams':list(teams)})
    if roster.empty:
        return 0
    rows = []
    for gid, (g, kickoff) in games.items():
        away = g.get('awayTeam',{}).get('abbrev')
        home = g.get('homeTeam',{}).get('abbrev')
        for p in roster[roster.team.isin((away,home))].itertuples():
            rows.append({'game_id':gid,'kickoff':kickoff,'Match':f'{away} @ {home}',
                         'Joueur':p.player_name,'player_id':p.player_id,'Équipe':p.team})
    ids = roster.player_id.astype(str).tolist()
    history = pd.read_sql_query('''WITH ranked AS (
       SELECT p.player_id,p.points,p.goals,
       ROW_NUMBER() OVER(PARTITION BY p.player_id ORDER BY p.game_date DESC,p.game_id DESC) rn
       FROM nhl_player_games p JOIN nhl_games g ON g.game_id=p.game_id
       WHERE g.game_state IN ('OFF','FINAL') AND g.start_time_utc < %(cutoff)s
       AND p.player_id::text = ANY(%(ids)s) AND p.points IS NOT NULL AND p.goals IS NOT NULL
    ) SELECT * FROM ranked WHERE rn <= 10''', conn, params={'cutoff':now,'ids':ids})
    picks = candidate_picks(rows, history)
    inserted = 0
    for profile in PROFILES:
        for pick in picks[profile]:
            # Unique key: a given model/profile/game is snapshotted once, even across reruns.
            with conn.cursor() as cur:
                cur.execute('''INSERT INTO v21_auto_picks
                    (profile,game_id,player_id,match_label,selection,market,probability,kickoff,created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (profile,game_id) DO NOTHING RETURNING id''',
                    (profile,pick['game_id'],pick['player_id'],pick['match'],pick['selection'],
                     pick['market'],pick['probability'],pick['time'],now))
                inserted += int(cur.fetchone() is not None)
    return inserted


def settle(conn):
    from settle_v14 import evaluate
    rows = conn.execute('''SELECT a.id,a.game_id,a.selection,g.home_team,g.away_team,g.home_score,g.away_score
        FROM v21_auto_picks a JOIN nhl_games g ON g.game_id=a.game_id
        WHERE a.status='pending' AND g.game_state IN ('OFF','FINAL')''').fetchall()
    for pid,gid,selection,home,away,hs,as_ in rows:
        players = conn.execute('SELECT player_name,goals,points FROM nhl_player_games WHERE game_id=%s',(gid,)).fetchall()
        outcome = evaluate(selection,(home,away,hs,as_),players)
        if outcome:
            conn.execute('UPDATE v21_auto_picks SET status=%s WHERE id=%s AND status=\'pending\'',(outcome,pid))
    return len(rows)


def main():
    with psycopg.connect(os.environ['SUPABASE_DB_URL']) as conn:
        created = generate(conn)
        settled = settle(conn)
    print(f'V21: {created} predictions added, {settled} pending predictions evaluated')


if __name__ == '__main__':
    main()
