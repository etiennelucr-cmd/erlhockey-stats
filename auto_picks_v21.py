"""Immutable daily automatic picks, separated from user-followed picks."""
import os
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import psycopg
import requests
from nhl_picks_v20 import candidate_picks, PROFILES
from espn_injuries_v19 import _matching_injury
from availability_v17 import _norm

PARIS = ZoneInfo('Europe/Paris')
PREFIX = 'Auto V21 | '
VERSION = 'V21.5'
log = logging.getLogger('erlhockey.v215')


def current_roster_ids(teams, session=None, roster_fetch=None):
    """Verified current NHL roster by team; fail closed if any team cannot be checked."""
    session = session or requests.Session()
    verified = {}
    for team in sorted(teams):
        if roster_fetch is None:
            response = session.get(f'https://api-web.nhle.com/v1/roster/{team}/current', timeout=25)
            response.raise_for_status()
            payload = response.json()
        else:
            payload = roster_fetch(team)
        if not isinstance(payload, dict) or not any(k in payload for k in ('forwards','defensemen','goalies')):
            raise ValueError(f'Roster NHL indisponible ou incomplet pour {team}')
        ids = set()
        for group in ('forwards','defensemen','goalies'):
            for player in payload.get(group, []):
                if player.get('id') is not None:
                    ids.add(str(player['id']))
        if not ids:
            raise ValueError(f'Aucun joueur NHL vérifié pour {team}')
        verified[team] = ids
    return verified



def injury_snapshot(conn, now, max_age_hours=24):
    """Use the existing ESPN collector snapshot; fail closed on stale/missing data.

    Do not silently treat an empty/failed injury feed as all players healthy.
    """
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT last_success_at, count FROM nhl_injury_sync_v19 WHERE id=1')
            meta = cur.fetchone()
            if not meta or not meta[0] or not meta[1] or meta[1] <= 0:
                raise RuntimeError('Aucune synchronisation ESPN valide')
            age = now - meta[0]
            if not timedelta(0) <= age <= timedelta(hours=max_age_hours):
                raise RuntimeError(f'Snapshot ESPN perime: {age}')
            cur.execute('SELECT player_name,team,status,detail FROM nhl_injury_reports_v19')
            entries = cur.fetchall()
        if not entries:
            raise RuntimeError('Table blessures ESPN vide')
        reports = {(_norm(name), _norm(team)): {'status': status, 'detail': detail}
                   for name, team, status, detail in entries}
        log.info('ESPN blessures: %d entrees, age %.1f h', len(reports), age.total_seconds()/3600)
        return reports
    except (psycopg.Error, RuntimeError) as exc:
        raise RuntimeError('Generation suspendue : blessures ESPN non verifiables. '
                           'Executer le workflow blessures-espn-v19 puis relancer V21.5. '
                           f'Detail: {exc}') from exc


def injury_eligible(name, team, reports):
    """Conservative: any ESPN injury listing excludes candidate; no listing != confirmed."""
    return _matching_injury(name, team, reports) is None


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


def generate(conn, now=None, fetch=None, roster_fetch=None):
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
    log.info('Matchs futurs detectes : %d', len(games))
    if not games:
        log.info('Aucun match eligible pour la fenetre Paris aujourd hui/demain')
        return 0
    teams = {team.get('abbrev') for g, _ in games.values() for team in (g.get('homeTeam', {}), g.get('awayTeam', {}))}
    teams.discard(None)
    # The historical last team is NOT evidence of current roster membership.
    # Stop rather than publish false picks if official rosters cannot be fetched.
    verified_rosters = current_roster_ids(teams, roster_fetch=roster_fetch)
    log.info('Equipes NHL verifiees : %d ; joueurs dans les effectifs : %d', len(verified_rosters), sum(map(len, verified_rosters.values())))
    injuries = injury_snapshot(conn, now)
    # Only finalized historical rows strictly before generation time: no look-ahead.
    # Current NHL roster is the source of truth; historic team can be stale after a transfer.
    roster_owner = {pid: team for team, members in verified_rosters.items() for pid in members}
    if len(roster_owner) != sum(map(len, verified_rosters.values())):
        raise ValueError('Un meme identifiant joueur apparait dans plusieurs effectifs officiels')
    roster = pd.read_sql_query('''SELECT DISTINCT ON (p.player_id) p.player_id,p.player_name,p.team
        FROM nhl_player_games p JOIN nhl_games g ON g.game_id=p.game_id
        WHERE g.game_state IN ('OFF','FINAL') AND g.start_time_utc < %(cutoff)s
        ORDER BY p.player_id,p.game_date DESC,p.game_id DESC''', conn,
        params={'cutoff':now,'teams':list(teams)})
    log.info('Joueurs historiques candidats : %d', len(roster))
    if roster.empty:
        log.warning('Aucun joueur historique disponible')
        return 0
    rows = []
    rejected = 0
    moved = 0
    injured = 0
    for gid, (g, kickoff) in games.items():
        away = g.get('awayTeam',{}).get('abbrev')
        home = g.get('homeTeam',{}).get('abbrev')
        for p in roster.itertuples():
            current_team = roster_owner.get(str(p.player_id))
            if current_team not in (away, home):
                rejected += 1
                continue
            if not injury_eligible(p.player_name, current_team, injuries):
                injured += 1
                continue
            if p.team != current_team:
                moved += 1
            rows.append({'game_id':gid,'kickoff':kickoff,'Match':f'{away} @ {home}',
                         'Joueur':p.player_name,'player_id':p.player_id,'Équipe':current_team})
    log.info('Candidatures valides : %d ; mauvaise equipe/effectif : %d ; blessure ESPN : %d ; transferts historiques corriges : %d', len(rows), rejected, injured, moved)
    if not rows:
        log.warning('Aucun joueur-match confirme dans les effectifs officiels')
        return 0
    ids = sorted({str(r['player_id']) for r in rows})
    history = pd.read_sql_query('''WITH ranked AS (
       SELECT p.player_id,p.points,p.goals,
       ROW_NUMBER() OVER(PARTITION BY p.player_id ORDER BY p.game_date DESC,p.game_id DESC) rn
       FROM nhl_player_games p JOIN nhl_games g ON g.game_id=p.game_id
       WHERE g.game_state IN ('OFF','FINAL') AND g.start_time_utc < %(cutoff)s
       AND p.player_id::text = ANY(%(ids)s) AND p.points IS NOT NULL AND p.goals IS NOT NULL
    ) SELECT * FROM ranked WHERE rn <= 10''', conn, params={'cutoff':now,'ids':ids})
    picks = candidate_picks(rows, history)
    # Defense in depth: the candidate algorithm must never bypass the official roster mapping.
    for profile, proposals in picks.items():
        for pick in proposals:
            game = games.get(int(pick['game_id']))
            if game is None:
                raise ValueError(f'Pick {profile}: match inconnu')
            fixture = game[0]
            valid_teams = {fixture.get('homeTeam', {}).get('abbrev'), fixture.get('awayTeam', {}).get('abbrev')}
            if roster_owner.get(str(pick['player_id'])) != pick['team'] or pick['team'] not in valid_teams:
                raise ValueError(f'Pick {profile}: association joueur-match non verifiee')
            if not injury_eligible(pick['player'], pick['team'], injuries):
                raise ValueError(f'Pick {profile}: joueur signale blesse par ESPN')
    log.info('Picks proposes : %d ; hors plage profil : %d', sum(map(len, picks.values())), sum(bool(p.get('fallback')) for values in picks.values() for p in values))
    inserted = 0
    duplicates = 0
    log.info('Source prioritaire: effectifs NHL officiels (api-web.nhle.com); Covers = recoupement manuel, non utilise automatiquement')
    log.info('Blessures ESPN filtrees (toute entree exclue); absence de signalement ne confirme PAS la participation')
    log.info('CBS Sports / Daily Faceoff: recoupement manuel seulement; pas de scraping automatique')
    for profile in PROFILES:
        for pick in picks[profile]:
            # Unique key: a given model/profile/game is snapshotted once, even across reruns.
            with conn.cursor() as cur:
                cur.execute('''INSERT INTO v21_auto_picks
                    (profile,game_id,player_id,match_label,selection,market,probability,kickoff,created_at,validation_state,validation_version,validation_note)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (profile,game_id) DO NOTHING RETURNING id''',
                    (profile,pick['game_id'],pick['player_id'],pick['match'],pick['selection'],
                     pick['market'],pick['probability'],pick['time'],now,'roster_injury_checked',VERSION,
                     'fallback_hors_plage' if pick.get('fallback') else 'dans_plage'))
                if cur.fetchone() is not None:
                    inserted += 1
                else:
                    duplicates += 1
    log.info('Picks ajoutes : %d ; doublons ignores : %d', inserted, duplicates)
    if duplicates:
        log.warning('%d picks deja presents ne sont pas remplaces, meme si leur joueur est suspect', duplicates)
    return inserted


def settle(conn):
    """Settle by official player ID rather than display name."""
    rows = conn.execute("""SELECT a.id,a.game_id,a.player_id,a.market,
        g.home_score,g.away_score
        FROM v21_auto_picks a JOIN nhl_games g ON g.game_id=a.game_id
        WHERE a.status='pending' AND g.game_state IN ('OFF','FINAL')""").fetchall()
    log.info('Picks pending avec match termine en base : %d', len(rows))
    settled = 0
    incomplete = 0
    for pick_id, gid, player_id, market, home_score, away_score in rows:
        if home_score is None or away_score is None:
            continue
        stats = conn.execute("""SELECT goals,points FROM nhl_player_games
            WHERE game_id=%s AND player_id::text=%s""", (gid, str(player_id))).fetchall()
        if len(stats) != 1 or stats[0][0] is None or stats[0][1] is None:
            # Une collecte manquante ne prouve pas une absence ou un pari annule.
            incomplete += 1
            continue
        elif market == '1+ but':
            outcome = 'won' if stats[0][0] >= 1 else 'lost'
        elif market == '1+ point':
            outcome = 'won' if stats[0][1] >= 1 else 'lost'
        elif market == '2+ points':
            outcome = 'won' if stats[0][1] >= 2 else 'lost'
        else:
            outcome = 'void'
        conn.execute("UPDATE v21_auto_picks SET status=%s WHERE id=%s AND status='pending'", (outcome, pick_id))
        settled += 1
    log.info('Picks evalues : %d ; en attente de statistiques fiables : %d', settled, incomplete)
    return settled


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')
    log.info('Demarrage %s : effectifs NHL, blessures ESPN, audit et reglement prudent', VERSION)
    with psycopg.connect(os.environ['SUPABASE_DB_URL']) as conn:
        settled = settle(conn)
        created = generate(conn)
    print(f'{VERSION}: {created} predictions added, {settled} pending predictions evaluated')


if __name__ == '__main__':
    main()
