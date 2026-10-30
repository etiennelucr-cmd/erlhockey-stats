"""V18: Reuse historically settled winning player markets for their next NHL games.

Only exact (player name, market) historical selections are matched. No past
outcome is presented as evidence of future success or a calibrated probability.
"""
from collections import defaultdict
from datetime import datetime, timezone
import math
import pandas as pd
import streamlit as st
from combo_v12 import fixtures, player_candidates, PARIS
from availability_v17 import load_availability, filter_player_picks
from tracker_v14 import connect, follow


def historical_results():
    """Only finalized legs; group by exact selection + market, avoiding cross-market leakage."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT selection, market, status, COUNT(*)
                           FROM tracked_legs WHERE status IN ('won','lost')
                           GROUP BY selection, market, status''')
            rows = cur.fetchall()
    counts = defaultdict(lambda: {'won': 0, 'lost': 0})
    for selection, market, status, count in rows:
        counts[(selection, market)][status] += int(count)
    return counts


def eligible_replays(picks, history, minimum_wins=1, minimum_rate=0.0):
    result = []
    for pick in picks:
        stats = history.get((pick['selection'], pick['market']))
        if not stats:
            continue
        wins, losses = stats['won'], stats['lost']
        settled = wins + losses
        if wins < minimum_wins or not settled or wins / settled < minimum_rate:
            continue
        result.append({**pick, 'past_wins': wins, 'past_losses': losses,
                       'past_rate': wins / settled, 'past_total': settled})
    return sorted(result, key=lambda p: (-p['past_wins'], -p['past_rate'],
                                         -p['probability'], p['selection']))


def make_combo(picks, count):
    """One selection per NHL fixture, no duplicate player or past-game replay."""
    selected = []
    used_games = set()
    for pick in picks:
        if pick['game_id'] in used_games:
            continue
        if pick['time'].astimezone(timezone.utc) <= datetime.now(timezone.utc):
            continue
        used_games.add(pick['game_id'])
        selected.append(pick)
        if len(selected) >= count:
            break
    return sorted(selected, key=lambda p: p['time'])


def show(db_query):
    st.caption('Réutilise les marchés joueurs gagnés dans tes anciens suivis lorsqu’ils ont un prochain match. Résultats passés ≠ garantie future.')
    period = st.radio('Période des prochains matchs', ['Ce soir', 'Demain', 'Mixte'], index=2,
                      horizontal=True, key='v18_winning_period')
    min_wins = st.number_input('Victoires historiques minimales pour une sélection', min_value=1,
                               max_value=100, value=1, step=1, key='v18_min_wins')
    min_rate = st.select_slider('Ratio historique minimal (gagnées / terminées)',
                                options=[0, 50, 60, 70, 80, 90, 100], value=0,
                                format_func=lambda x: f'{x} %', key='v18_min_rate') / 100
    upcoming = fixtures(db_query, datetime.now(PARIS), period)
    if upcoming.empty:
        st.info('Aucun prochain match disponible pour cette période.')
        return
    try:
        history = historical_results()
    except Exception as exc:
        st.error('Historique Supabase inaccessible. Vérifie SUPABASE_DB_URL et les tables V14.')
        st.caption(type(exc).__name__)
        return
    if not history:
        st.info('Aucune sélection terminée dans tracked_legs. Suis des combinés et attends leur règlement pour activer ce générateur.')
        return
    try:
        picks = player_candidates(db_query, upcoming, window=10)
    except Exception as exc:
        st.error('Impossible de récupérer les statistiques joueurs NHL.')
        st.caption(type(exc).__name__)
        return
    # V17 strict availability: no unconfirmed player is silently promoted.
    picks, excluded, unknown = filter_player_picks(picks, load_availability(), strict=True)
    st.caption(f'Présences V17 : {len(excluded)} choix exclus pour indisponibilité ; '
               f'{len(unknown)} non confirmés exclus. Statuts issus du CSV local, non actualisés automatiquement.')
    matches = eligible_replays(picks, history, int(min_wins), min_rate)
    if not matches:
        st.warning('Aucune ancienne sélection gagnante éligible pour ces matchs. Vérifie les statuts joueurs et/ou réduis les seuils.')
        return
    distinct = len({p['game_id'] for p in matches})
    st.metric('Matchs avec sélection historique éligible', distinct)
    rows = [{'Prochain match (Paris)': p['time'].strftime('%d/%m %H:%M'),
             'Match': p['match'], 'Sélection historique': p['selection'],
             'Gagnées': p['past_wins'], 'Perdues': p['past_losses'],
             'Ratio historique': f"{p['past_rate']:.1%}",
             'Forme récente': p['detail']} for p in matches]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if distinct < 2:
        st.info('Au moins deux rencontres distinctes sont nécessaires pour créer un combiné.')
        return
    count = st.select_slider('Nombre de sélections du combiné', options=list(range(2, distinct + 1)),
                             value=min(5, distinct), key='v18_winning_count')
    combo = make_combo(matches, count)
    if len(combo) < count:
        st.warning('Pas assez de matchs non commencés pour construire le combiné demandé.')
        return
    st.subheader('🏆 Combiné issu des sélections gagnantes')
    st.dataframe(pd.DataFrame([{'Heure (Paris)': p['time'].strftime('%d/%m %H:%M'),
                                'Match': p['match'], 'Sélection': p['selection'],
                                'Historique': f"{p['past_wins']} G / {p['past_losses']} P",
                                'Ratio': f"{p['past_rate']:.1%}",
                                'Forme': p['detail']} for p in combo]),
                 hide_index=True, use_container_width=True)
    st.caption('Le ratio historique est descriptif, non une probabilité prédictive. '
               'Les estimations de forme ne sont pas calibrées. Aucun pari n’est placé automatiquement.')
    if st.button('☑️ Suivre ce combiné historique', key='v18_follow_winning'):
        try:
            saved = follow('Sélections gagnantes V18', combo)
            st.success('Combiné enregistré dans Supabase.' if saved else 'Ce combiné est déjà suivi.')
        except ValueError as exc:
            st.warning(str(exc))
        except Exception:
            st.error('Impossible de sauvegarder le combiné dans Supabase.')
