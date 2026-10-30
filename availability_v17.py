"""Conservative player availability filter using an explicit, timestamped CSV feed.

No assertion that a player is healthy is made without a fresh affirmative status.
The CSV is maintained by the operator; no live injury feed is implied.
"""
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unicodedata

DEFAULT_FILE = Path(__file__).with_name('player_availability_v17.csv')
GOOD = {'confirmed', 'active', 'available', 'playing'}
BAD = {'out', 'injured', 'ir', 'ltir', 'suspended', 'day-to-day', 'dtd', 'game-time decision', 'gtd', 'questionable', 'doubtful', 'inactive', 'scratched'}

def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    return ' '.join(''.join(c for c in s if not unicodedata.combining(c)).casefold().split())

def load_availability(path=DEFAULT_FILE, max_age_hours=24, now=None):
    now = now or datetime.now(timezone.utc)
    entries = {}
    if not Path(path).is_file():
        return entries
    with open(path, newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            name = _norm(row.get('player_name'))
            team = _norm(row.get('team'))
            if not name or not team:
                continue
            status = _norm(row.get('status'))
            try:
                checked = datetime.fromisoformat((row.get('checked_at_utc') or '').replace('Z', '+00:00'))
                if checked.tzinfo is None:
                    continue
                age = now - checked.astimezone(timezone.utc)
                fresh = timedelta(0) <= age <= timedelta(hours=max_age_hours)
            except ValueError:
                fresh = False
            entries[(name, team)] = {'status': status, 'fresh': fresh, 'checked_at_utc': row.get('checked_at_utc', '')}
    return entries

def player_status(name, team, entries):
    item = entries.get((_norm(name), _norm(team)))
    if not item or not item['fresh']:
        return 'unknown'
    if item['status'] in GOOD:
        return 'confirmed'
    if item['status'] in BAD:
        return 'excluded'
    return 'unknown'

def filter_player_picks(picks, entries, strict=True):
    eligible, excluded, unknown = [], [], []
    for pick in picks:
        status = player_status(pick.get('player_name'), pick.get('team'), entries)
        if status == 'excluded':
            excluded.append(pick)
        elif status == 'unknown':
            unknown.append(pick)
            if not strict:
                eligible.append({**pick, 'caveat': 'Statut joueur non confirmé — vérifier avant le match'})
        else:
            eligible.append({**pick, 'caveat': 'Présence indiquée comme confirmée dans le fichier de vérification (pas une garantie)'})
    return eligible, excluded, unknown
