"""ESPN injury snapshot. Injury listings are NOT proof that unlisted players will play."""
import os
import re
from datetime import datetime, timezone, timedelta
from io import StringIO
import pandas as pd
import requests
import psycopg
from availability_v17 import _norm

URL = 'https://www.espn.com/nhl/injuries'
API_URL = 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries'
TEAM_ALIASES = {'anaheim ducks':'ANA','boston bruins':'BOS','buffalo sabres':'BUF',
'calgary flames':'CGY','carolina hurricanes':'CAR','chicago blackhawks':'CHI',
'colorado avalanche':'COL','columbus blue jackets':'CBJ','dallas stars':'DAL',
'detroit red wings':'DET','edmonton oilers':'EDM','florida panthers':'FLA',
'los angeles kings':'LAK','minnesota wild':'MIN','montreal canadiens':'MTL',
'nashville predators':'NSH','new jersey devils':'NJD','new york islanders':'NYI',
'new york rangers':'NYR','ottawa senators':'OTT','philadelphia flyers':'PHI',
'pittsburgh penguins':'PIT','san jose sharks':'SJS','seattle kraken':'SEA',
'st louis blues':'STL','tampa bay lightning':'TBL','toronto maple leafs':'TOR',
'utah mammoth':'UTA','utah hockey club':'UTA','vancouver canucks':'VAN',
'vegas golden knights':'VGK','washington capitals':'WSH','winnipeg jets':'WPG'}

SCHEMA = '''CREATE TABLE IF NOT EXISTS nhl_injury_reports_v19 (
 player_name TEXT NOT NULL, team TEXT NOT NULL, status TEXT NOT NULL,
 detail TEXT, checked_at_utc TIMESTAMPTZ NOT NULL,
 PRIMARY KEY(player_name,team));
 CREATE TABLE IF NOT EXISTS nhl_injury_sync_v19 (
 id INTEGER PRIMARY KEY CHECK (id=1), checked_at_utc TIMESTAMPTZ,
 last_success_at TIMESTAMPTZ, source TEXT, error TEXT, count INTEGER NOT NULL DEFAULT 0);'''

def parse_espn(html):
    """Parse ESPN injury tables, including team labels outside h2/h3 headings.

    A page with no recognizable team-linked injury rows is NEVER a valid snapshot.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    reports = []
    for table in soup.find_all('table'):
        headers = [_norm(c.get_text(' ', strip=True)) for c in table.select('thead th')]
        if not headers:
            first = table.find('tr')
            headers = [_norm(c.get_text(' ', strip=True)) for c in first.find_all(['th','td'], recursive=False)] if first else []
        if not any('status' in h for h in headers):
            continue
        # ESPN sometimes renders the team name in a div or link instead of a heading.
        team = None
        node = table
        for _ in range(12):
            node = node.find_previous(['h2','h3','h4','a','div','span'])
            if node is None:
                break
            label = _norm(node.get_text(' ', strip=True))
            if len(label) > 90:
                continue
            team = next((abbr for name,abbr in TEAM_ALIASES.items() if label == name or label.startswith(name + ' ')), None)
            if team:
                break
        if not team:
            continue
        for tr in table.select('tbody tr'):
            cells = tr.find_all(['td','th'], recursive=False)
            if len(cells) != len(headers):
                continue
            row = dict(zip(headers, [c.get_text(' ', strip=True) for c in cells]))
            name = row.get('name') or row.get('player') or ''
            status = row.get('status') or ''
            if name and status:
                reports.append((name,team,status,row.get('comment','') or row.get('details','')))
    if not reports:
        raise ValueError('Aucune ligne de blessure NHL exploitable dans la page ESPN (blocage ou format modifié).')
    return list({(_norm(n),t):(n,t,s,d) for n,t,s,d in reports}.values())


def parse_espn_api(payload):
    """Parse ESPN league injury JSON; reject unrecognized/empty responses.

    This endpoint is unofficial and can change without notice.
    """
    if not isinstance(payload, dict):
        raise ValueError('Réponse JSON ESPN non reconnue')
    groups = payload.get('injuries') or payload.get('items') or []
    if not isinstance(groups, list) or not groups:
        raise ValueError('API ESPN sans groupes de blessures exploitables')
    reports = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        team_obj = group.get('team') or {}
        if isinstance(team_obj, str):
            team_obj = {'displayName': team_obj}
        team_name = str(team_obj.get('displayName') or team_obj.get('name') or group.get('displayName') or '')
        abbr = str(team_obj.get('abbreviation') or '').upper()
        if abbr not in set(TEAM_ALIASES.values()):
            abbr = TEAM_ALIASES.get(_norm(team_name))
        if not abbr:
            continue
        entries = group.get('injuries') or group.get('items') or []
        if not isinstance(entries, list):
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            athlete = item.get('athlete') or {}
            if isinstance(athlete, str):
                athlete = {'displayName': athlete}
            name = athlete.get('displayName') or athlete.get('fullName') or item.get('name')
            status_obj = item.get('status') or item.get('type') or item.get('injuryStatus') or ''
            status = (status_obj.get('name') or status_obj.get('description') or status_obj.get('type') or '') if isinstance(status_obj,dict) else str(status_obj)
            detail = item.get('details') or item.get('description') or item.get('comment') or ''
            if isinstance(detail,dict):
                detail = detail.get('detail') or detail.get('description') or ''
            if name and status:
                reports.append((str(name),abbr,str(status),str(detail)))
    if not reports:
        raise ValueError('API ESPN: aucun joueur blessé identifiable (schéma modifié ou données vides)')
    return list({(_norm(n),t):(n,t,s,d) for n,t,s,d in reports}.values())


def fetch_reports():
    """Prefer ESPN JSON; fall back to HTML. Never accept empty as success."""
    headers = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
               'Accept':'application/json,text/html;q=0.9', 'Accept-Language':'en-US,en;q=0.9'}
    failures=[]
    try:
        response=requests.get(API_URL,headers=headers,timeout=25)
        response.raise_for_status()
        reports=parse_espn_api(response.json())
        print(f'ESPN API JSON: {len(reports)} blessures valides')
        return reports
    except (requests.RequestException,ValueError,TypeError) as exc:
        failures.append(f'API JSON: {type(exc).__name__}: {str(exc)[:180]}')
    try:
        response=requests.get(URL,headers=headers,timeout=25)
        response.raise_for_status()
        html=response.text
        if len(html)<1000 or any(token in html.lower() for token in ('captcha-delivery.com','cf-chl-','access denied')):
            raise ValueError('page bloquée ou incomplète')
        reports=parse_espn(html)
        print(f'ESPN HTML: {len(reports)} blessures valides')
        return reports
    except (requests.RequestException,ValueError) as exc:
        failures.append(f'HTML: {type(exc).__name__}: {str(exc)[:180]}')
    raise RuntimeError('Synchronisation ESPN impossible. ' + ' | '.join(failures))

def sync():
    db = os.environ['SUPABASE_DB_URL']
    now = datetime.now(timezone.utc)
    try:
        reports = fetch_reports()
        with psycopg.connect(db) as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
                cur.execute('DELETE FROM nhl_injury_reports_v19')
                cur.executemany('INSERT INTO nhl_injury_reports_v19 (player_name,team,status,detail,checked_at_utc) VALUES (%s,%s,%s,%s,%s)', [(*r,now) for r in reports])
                cur.execute('''INSERT INTO nhl_injury_sync_v19 (id,checked_at_utc,last_success_at,source,error,count)
                 VALUES (1,%s,%s,%s,NULL,%s) ON CONFLICT(id) DO UPDATE SET
                 checked_at_utc=EXCLUDED.checked_at_utc,last_success_at=EXCLUDED.last_success_at,
                 source=EXCLUDED.source,error=NULL,count=EXCLUDED.count''',(now,now,URL,len(reports)))
        print(f'ESPN: {len(reports)} blessures enregistrées')
    except Exception as exc:
        # Keep previous snapshot but mark attempted refresh as failed.
        with psycopg.connect(db) as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
                cur.execute('''INSERT INTO nhl_injury_sync_v19(id,checked_at_utc,source,error,count)
                 VALUES (1,%s,%s,%s,0) ON CONFLICT(id) DO UPDATE SET
                 checked_at_utc=EXCLUDED.checked_at_utc,error=EXCLUDED.error''',(now,URL,str(exc)[:500]))
        raise

def load_injury_reports(max_age_hours=24):
    """Return reports and freshness. Database outage means NOT VERIFIED."""
    try:
        with psycopg.connect(os.environ['SUPABASE_DB_URL'],connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT last_success_at,error,count FROM nhl_injury_sync_v19 WHERE id=1')
                meta=cur.fetchone()
                if not meta or not meta[0]:
                    return {},False,'Aucune synchronisation ESPN réussie'
                fresh=timedelta(0) <= datetime.now(timezone.utc)-meta[0] <= timedelta(hours=max_age_hours)
                if not fresh:
                    return {},False,'Données ESPN périmées'
                cur.execute('SELECT player_name,team,status,detail FROM nhl_injury_reports_v19')
                rows=cur.fetchall()
                return {(_norm(n),_norm(t)):{'status':s,'detail':d} for n,t,s,d in rows},True,('ESPN synchronisé' if not meta[1] else 'Dernière tentative ESPN en échec ; snapshot récent conservé')
    except Exception as exc:
        return {},False,f'Statuts ESPN indisponibles : {type(exc).__name__}'

def _matching_injury(name, team, reports):
    """Match full names and NHL abbreviated first names, within the same team.

    Ambiguous matches are treated as an injury flag (conservative); no fuzzy
    matching across teams. Normalization is shared with the player database.
    """
    import re
    target = _norm(name or '')
    club = _norm(team or '')
    direct = reports.get((target, club))
    if direct:
        return direct
    parts = target.replace('.', ' ').split()
    if len(parts) < 2:
        return None
    initial, surname = parts[0][0], ' '.join(parts[1:])
    for (injured_name, injured_team), report in reports.items():
        if injured_team != club:
            continue
        tokens = injured_name.replace('.', ' ').split()
        if len(tokens) >= 2 and tokens[0][0] == initial and ' '.join(tokens[1:]) == surname:
            return report
    return None


def apply_injury_filter(picks, strict=False):
    """Standard: exclude ESPN-listed players; strict: require manual confirmation.

    An unlisted player is NEVER described as officially confirmed. Stale ESPN
    snapshots do not authorize unconfirmed players, in either mode.
    """
    from availability_v17 import load_availability, player_status
    reports, fresh, message = load_injury_reports()
    manual = load_availability()
    eligible, excluded, unknown = [], [], []
    for pick in picks:
        name = pick.get('player_name') or pick.get('Joueur')
        team = pick.get('team') or pick.get('Équipe')
        injury = _matching_injury(name, team, reports) if fresh else None
        manual_status = player_status(name, team, manual)
        if injury or manual_status == 'excluded':
            reason = ('ESPN : ' + str(injury.get('status', 'indisponible'))) if injury else 'Exclu dans le CSV'
            excluded.append({**pick, 'availability_reason': reason})
        elif manual_status == 'confirmed':
            eligible.append({**pick, 'caveat': 'Présence déclarée dans le CSV ; vérifier la composition officielle'})
        else:
            unknown.append(pick)
            if fresh and not strict:
                eligible.append({**pick, 'caveat': 'Non listé blessé par ESPN ; présence NON confirmée'})
    return eligible, excluded, unknown, fresh, message

if __name__=='__main__':
    sync()
