"""Rattrapage ponctuel des matchs NHL 2026-2027 vers Supabase.

Lancer une seule fois via GitHub Actions (workflow manuel).
La collecte habituelle collect_nhl.py reste inchangée.
"""
import logging
import os
from datetime import date, datetime, timedelta, timezone

import psycopg

from collect_nhl import collect_day

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("nhl-backfill")

# Commencer suffisamment tôt pour couvrir le début de saison.
START = date(2026, 10, 1)


def main():
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("Secret SUPABASE_DB_URL manquant")

    # Ne pas reprendre les huit derniers jours : la collecte planifiée s'en charge.
    end = datetime.now(timezone.utc).date() - timedelta(days=8)
    if end < START:
        LOG.info("Aucune date ancienne à rattraper pour le moment")
        return

    days = (end - START).days + 1
    LOG.info("Rattrapage de %s jours : %s à %s", days, START, end)
    total_games = total_players = 0
    failures = []
    with psycopg.connect(url, connect_timeout=20, autocommit=True) as conn:
        for offset in range(days):
            day = (START + timedelta(days=offset)).isoformat()
            try:
                games, players = collect_day(conn, day)
                total_games += games
                total_players += players
            except Exception as exc:
                LOG.exception("Échec du rattrapage pour %s", day)
                failures.append(day)

    LOG.info("Rattrapage : %s matchs, %s lignes joueurs", total_games, total_players)
    if failures:
        raise RuntimeError("Dates non collectées : " + ", ".join(failures))


if __name__ == "__main__":
    main()
