"""Collecte NHL vers Supabase. Exécution prévue par GitHub Actions."""
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import psycopg
import requests

API = "https://api-web.nhle.com/v1"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("nhl")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ErlHockeyStats/1.0"})


def fetch(path):
    for attempt in range(3):
        try:
            response = SESSION.get(f"{API}/{path}", timeout=25)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def team_code(team):
    return team.get("abbrev") or team.get("commonName", {}).get("default") or "?"


def player_name(player):
    """Le boxscore NHL fournit normalement name.default, pas firstName/lastName."""
    def label(value):
        if isinstance(value, dict):
            return value.get("default") or value.get("fr") or ""
        return str(value or "")

    name = label(player.get("name")).strip()
    if not name:
        name = (label(player.get("firstName")) + " " + label(player.get("lastName"))).strip()
    return name or str(player["playerId"])


def collect_day(conn, day):
    data = fetch(f"score/{day}")
    games = data.get("games", [])
    saved_games = saved_players = 0
    for game in games:
        game_id = game.get("id")
        if not game_id:
            continue
        state = game.get("gameState", "")
        game_date = game.get("gameDate") or day
        with conn.transaction():
            conn.execute("""
                INSERT INTO nhl_games
                  (game_id, game_date, start_time_utc, home_team, away_team,
                   home_score, away_score, game_state, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (game_id) DO UPDATE SET
                  game_date=EXCLUDED.game_date,
                  start_time_utc=EXCLUDED.start_time_utc,
                  home_team=EXCLUDED.home_team, away_team=EXCLUDED.away_team,
                  home_score=EXCLUDED.home_score, away_score=EXCLUDED.away_score,
                  game_state=EXCLUDED.game_state, updated_at=NOW()
            """, (game_id, game_date, game.get("startTimeUTC"),
                  team_code(game.get("homeTeam") or {}),
                  team_code(game.get("awayTeam") or {}),
                  (game.get("homeTeam") or {}).get("score"),
                  (game.get("awayTeam") or {}).get("score"), state))
        saved_games += 1
        # Les statistiques ne sont définitives qu'après la fin officielle du match.
        if state not in {"OFF", "FINAL"}:
            continue
        try:
            box = fetch(f"gamecenter/{game_id}/boxscore")
            groups = box.get("playerByGameStats") or {}
            if not groups:
                LOG.warning("Boxscore vide pour %s", game_id)
                continue
            with conn.transaction():
                for side in ("homeTeam", "awayTeam"):
                    team = team_code(game.get(side) or {})
                    roster = groups.get(side) or {}
                    for position in ("forwards", "defense"):
                        for player in roster.get(position, []):
                            pid = player.get("playerId")
                            if pid is None:
                                continue
                            goals = int(player.get("goals") or 0)
                            assists = int(player.get("assists") or 0)
                            conn.execute("""
                                INSERT INTO nhl_player_games
                                  (game_id, player_id, player_name, team,
                                   game_date, goals, assists, points, updated_at)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                                ON CONFLICT (game_id, player_id) DO UPDATE SET
                                  player_name=EXCLUDED.player_name,
                                  team=EXCLUDED.team, game_date=EXCLUDED.game_date,
                                  goals=EXCLUDED.goals, assists=EXCLUDED.assists,
                                  points=EXCLUDED.points, updated_at=NOW()
                            """, (game_id, pid, player_name(player), team,
                                  game_date, goals, assists, goals + assists))
                            saved_players += 1
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            LOG.warning("Statistiques indisponibles pour %s: %s", game_id, exc)
    LOG.info("%s : %s matchs, %s lignes joueurs", day, saved_games, saved_players)
    return saved_games, saved_players


def main():
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("Secret SUPABASE_DB_URL manquant")
    today = datetime.now(timezone.utc).date()
    # Fenêtre glissante : couvre les matchs nord-américains autour de minuit UTC.
    dates = [(today + timedelta(days=offset)).isoformat() for offset in range(-7, 2)]
    total_games = total_players = 0
    errors = []
    with psycopg.connect(url, connect_timeout=20, autocommit=True) as conn:
        for day in dates:
            try:
                games, players = collect_day(conn, day)
                total_games += games
                total_players += players
            except Exception as exc:
                LOG.exception("Erreur collecte %s", day)
                errors.append(f"{day}: {exc}")
        if not errors:
            conn.execute("""
                INSERT INTO nhl_sync_status (source, last_success_at, details)
                VALUES ('nhl_api', NOW(), %s)
                ON CONFLICT (source) DO UPDATE SET
                  last_success_at=NOW(), details=EXCLUDED.details
            """, (f"{total_games} matchs, {total_players} lignes joueurs; fenêtre de 9 jours",))
    if errors:
        raise RuntimeError("Échec partiel de la collecte : " + "; ".join(errors))
    LOG.info("Collecte terminée : %s matchs, %s lignes joueurs", total_games, total_players)


if __name__ == "__main__":
    main()
