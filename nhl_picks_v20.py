"""V20 NHL Picks: reproducible per-profile player-market suggestions and tracked outcomes."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import math
import html
import pandas as pd
import streamlit as st
from tracker_v14 import follow, connect
from ui_format_v22 import STATUSES

PROFILES = ('Prudent', 'Modéré', 'Équilibré', 'Risqué', 'Ultra risqué')
MARKETS = (('1+ point', 'points', 1), ('2+ points', 'points', 2), ('1+ but', 'goals', 1))
PARIS = ZoneInfo('Europe/Paris')

def filter_games_by_period(rows, period, now=None):
    """NHL evening in Paris: 18:00 through 11:59 the next day.

    This groups overnight North American games with the preceding Paris evening,
    while preserving exact local kickoff dates in the display.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    local_now = now.astimezone(PARIS)
    today = local_now.date()
    def night_date(dt):
        local = dt.astimezone(PARIS)
        return local.date() - timedelta(days=1) if local.hour < 12 else local.date()
    targets = ({today} if period == 'Ce soir' else
               {today + timedelta(days=1)} if period == 'Demain' else
               {today, today + timedelta(days=1)} if period == 'Mixte' else set())
    return [r for r in rows if isinstance(r.get('kickoff'), datetime)
            and r['kickoff'].tzinfo is not None and r['kickoff'] > now
            and night_date(r['kickoff']) in targets]


def paris_time_label(dt):
    local = dt.astimezone(PARIS)
    return local.strftime('%d/%m/%Y · %Hh%M')


def pct_label(probability):
    return f'{probability * 100:.1f}'.replace('.', ',') + ' %'

RANGES = {'Prudent':(.72,1.0), 'Modéré':(.62,.82), 'Équilibré':(.50,.72),
          'Risqué':(.35,.60), 'Ultra risqué':(.15,.45)}


def consecutive_streak(values, threshold):
    """Signed streak: positive = consecutive hits, negative = consecutive misses."""
    numbers = pd.to_numeric(pd.Series(values), errors='coerce').dropna().tolist()
    if not numbers:
        return 0
    hit = numbers[0] >= threshold
    length = 0
    for value in numbers:
        if (value >= threshold) != hit:
            break
        length += 1
    return length if hit else -length


def opponent_defense(games_frame):
    """Recent goals conceded per team, from final NHL games only; descriptive, not calibrated."""
    if games_frame is None or games_frame.empty:
        return {}
    frame = games_frame.copy()
    for column in ('home_score', 'away_score'):
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    frame = frame.dropna(subset=['home_score', 'away_score']).sort_values('game_date', ascending=False)
    teams = {}
    for _, game in frame.iterrows():
        for team, conceded in ((game['home_team'], game['away_score']), (game['away_team'], game['home_score'])):
            if pd.isna(team):
                continue
            teams.setdefault(str(team), []).append(float(conceded))
    return {team: {'games': len(values[:10]), 'goals_against_avg': sum(values[:10]) / len(values[:10])}
            for team, values in teams.items() if values}


def candidate_picks(rows, history, max_per_profile=None, min_games=5, defense=None):
    """One suggested player pick per eligible game and profile.

    Prefer a distinct player across profiles for a given game where possible.
    Profile ranges are preferences, not eligibility filters: a fallback is
    explicitly marked when no candidate is inside the target range.
    """
    results = {name: [] for name in PROFILES}
    defense = defense or {}
    if history.empty:
        return results
    grouped = {str(pid): frame.sort_values('rn') for pid, frame in history.groupby('player_id')}
    games = {}
    for row in rows:
        hist = grouped.get(str(row.get('player_id')))
        if hist is None or len(hist) < min_games:
            continue
        game_id, kickoff = row.get('game_id'), row.get('kickoff')
        if game_id is None or not isinstance(kickoff, datetime) or kickoff.tzinfo is None:
            continue
        for market, column, threshold in MARKETS:
            vals = pd.to_numeric(hist[column], errors='coerce').dropna().head(10)
            if len(vals) < min_games:
                continue
            hits = int((vals >= threshold).sum())
            probability = (hits + 1) / (len(vals) + 2)
            item = {'game_id': int(game_id), 'time': kickoff, 'match': row['Match'],
                    'selection': f"{row['Joueur']} — {market}", 'market': market,
                    'probability': probability, 'hits': hits, 'sample': len(vals),
                    'player': row['Joueur'], 'player_id': str(row['player_id']),
                    'team': row['Équipe'],
                    'opponent': row.get('Adversaire', ''),
                    'opponent_defense': defense.get(str(row.get('Adversaire', ''))),
                    'point_streak': consecutive_streak(hist['points'].head(10), 1),
                    'goal_streak': consecutive_streak(hist['goals'].head(10), 1),
                    'market_streak': consecutive_streak(vals, threshold),
                    'recent_values': [int(v) for v in vals.tolist()],
                    'hits_5': int((vals.head(5) >= threshold).sum()),
                    'sample_5': min(5, len(vals))}
            games.setdefault(int(game_id), []).append(item)
    for game_id, options in sorted(games.items(), key=lambda pair: (pair[1][0]['time'], pair[0])):
        used_players = set()
        for name in PROFILES:
            lo, hi = RANGES[name]
            center = (lo + hi) / 2
            # A profile always gets a candidate when a game has eligible players.
            # Prefer in-range picks, then distinct players, then proximity to target.
            ranked = sorted(options, key=lambda x: (
                x['player_id'] in used_players,
                not (lo <= x['probability'] <= hi),
                abs(x['probability'] - center),
                -x['probability'], x['player_id'], x['market']))
            choice = dict(ranked[0])
            choice['in_profile_range'] = lo <= choice['probability'] <= hi
            choice['fallback'] = not choice['in_profile_range']
            choice['player_reused'] = choice['player_id'] in used_players
            results[name].append(choice)
            used_players.add(choice['player_id'])
    if max_per_profile is not None:
        for name in PROFILES:
            results[name] = results[name][:max_per_profile]
    return results


def history_summary():
    with connect() as conn:
        return pd.read_sql_query("""SELECT c.profile, c.created_at, l.selection, l.status,
            l.probability, l.kickoff FROM tracked_combos c
            JOIN tracked_legs l ON l.combo_id=c.id
            WHERE c.profile LIKE 'NHL Picks V20 | %%'
            ORDER BY c.created_at DESC""", conn)


def show(rows, db_query):
    from auto_dashboard_v21 import show as show_v21
    show_v21()
    st.caption('Sélections automatiques par profil, calculées avec les statistiques antérieures. '
               'Ce sont des estimations exploratoires non calibrées, et non des prédictions personnelles en temps réel de ChatGPT.')
    st.warning('Une montante/descendante peut amplifier rapidement les pertes. '
               'Le suivi ci-dessous est statistique : aucune mise ni progression automatique.')
    period = st.radio('Matchs à afficher', ('Ce soir', 'Demain', 'Mixte'),
                      horizontal=True, key='picks20_period',
                      help='Dates calculées en heure de Paris. Mixte = aujourd’hui et demain.')
    st.caption('Soirée NHL : de 12h00 à 11h59 le lendemain, heure de Paris. Les matchs après minuit restent dans la soirée précédente. Chaque horaire affiche sa date française exacte.')
    rows = filter_games_by_period([r for r in rows if r.get('game_id') is not None], period)
    if rows:
        st.caption(f'🏒 {len(set(r["game_id"] for r in rows))} rencontres futures · horaires Europe/Paris')
        ids = sorted({int(r['player_id']) for r in rows})
        history = db_query("""WITH ranked AS (
            SELECT p.player_id,p.points,p.goals,
              ROW_NUMBER() OVER(PARTITION BY p.player_id ORDER BY p.game_date DESC,p.game_id DESC) rn
            FROM nhl_player_games p JOIN nhl_games g ON g.game_id=p.game_id
            WHERE g.game_state IN ('OFF','FINAL') AND p.player_id=ANY(%s)
              AND p.points IS NOT NULL AND p.goals IS NOT NULL
        ) SELECT * FROM ranked WHERE rn<=10""", (ids,))
        # Independent descriptive opponent metric: last 10 final games, not used as a probability multiplier.
        try:
            recent_games = db_query("""SELECT game_date, home_team, away_team, home_score, away_score
                FROM nhl_games WHERE game_state IN ('OFF','FINAL')
                AND home_score IS NOT NULL AND away_score IS NOT NULL
                ORDER BY game_date DESC LIMIT 600""")
            defense = opponent_defense(recent_games)
        except Exception:
            defense = {}
            st.caption('Statistiques défensives adverses indisponibles ; suggestions calculées sans ce contexte.')
        candidates = candidate_picks(rows, history, defense=defense)
    else:
        candidates = {name:[] for name in PROFILES}
        st.info('Aucune rencontre future éligible pour cette soirée. Essaie « Mixte » ou « Demain ». Si des effectifs NHL sont indisponibles, seuls les joueurs vérifiés peuvent apparaître.')
    try:
        past = history_summary()
    except Exception:
        past = pd.DataFrame()
        st.warning('Historique indisponible : vérifie la connexion Supabase et le schéma tracker V14.')
    summary=[]
    for name in PROFILES:
        subset = past[past.profile == f'NHL Picks V20 | {name}'] if not past.empty else pd.DataFrame()
        won = int((subset.status=='won').sum()) if not subset.empty else 0
        lost = int((subset.status=='lost').sum()) if not subset.empty else 0
        summary.append({'Profil':name,'Suivies':len(subset),'Gagnées':won,'Perdues':lost,
                        'Réussite':f'{won/(won+lost):.1%}' if won+lost else '—',
                        'Proposés':len(candidates[name])})
    st.subheader('Bilan des picks suivis')
    st.caption('Un pick par match et par profil, si au moins un joueur possède assez de données. Les profils peuvent proposer des joueurs différents du même match.')
    st.dataframe(pd.DataFrame(summary),hide_index=True,width='stretch')
    st.caption('Le taux est calculé uniquement sur les picks suivis et réglés. '
               'Une sélection non suivie n’entre pas dans les résultats. Sans cotes et mises, aucun ROI ne peut être calculé.')
    st.subheader(f'🎯 Choisir mes picks · {period}')
    st.caption('🕒 Heure française exacte · estimation du modèle distincte des réussites historiques · coche puis confirme tes choix.')
    st.caption('Coche uniquement les picks que tu as choisis, ou utilise « All » pour sélectionner tous les picks proposés du profil. Le suivi est enregistré seulement après confirmation.')
    for name in PROFILES:
        picks = candidates[name]
        with st.expander(f'{name} · {len(picks)} suggestions', expanded=name=='Prudent'):
            if not picks:
                st.info('Aucune suggestion vérifiée pour cette période. Essaie « Mixte » ou attends les prochaines rencontres.')
                continue
            all_key = f'picks20_all_{name}'
            selected_keys = [f'picks20_choose_{name}_{p["game_id"]}_{p["player_id"]}_{p["market"]}' for p in picks]
            # A profile-wide checkbox controls the individual selection checkboxes.
            def set_all(keys=tuple(selected_keys), master=all_key):
                for key in keys:
                    st.session_state[key] = st.session_state[master]
            st.checkbox('All — sélectionner tous les picks de ce profil', key=all_key,
                        on_change=set_all)
            for i, p in enumerate(picks):
                with st.container(border=True):
                    c1, c2 = st.columns([5, 2], vertical_alignment='center')
                    with c1:
                        st.markdown(f"<div class='eh-pick-match'><span class='eh-match-title'>🏒 {html.escape(str(p['match']))}</span><span class='eh-match-time'>🕒 {html.escape(paris_time_label(p['time']))} · Paris</span></div>", unsafe_allow_html=True)
                        st.checkbox(p['selection'], key=selected_keys[i])
                        if p['fallback']:
                            st.caption('⚠️ Hors plage de probabilité habituelle du profil')
                        if p['player_reused']:
                            st.caption('↗️ Joueur également proposé dans un autre profil')
                    with c2:
                        st.markdown(f"<div class='eh-pick-prob'>{pct_label(p['probability'])}</div><div class='eh-pick-prob-caption'>Estimation du modèle · non calibrée</div>",unsafe_allow_html=True)
                        st.progress(float(p['probability']))
                        st.caption(f"Historique marché : {p['hits']}/{p['sample']} sur 10 matchs · {p['hits_5']}/{p['sample_5']} sur 5 matchs")
                    st.caption(f"Série marché : {p['market_streak']:+d} · Points : {p['point_streak']:+d} · Buts : {p['goal_streak']:+d} (positif = réussite, négatif = échec)")
                    with st.expander('📊 Forme récente et adversaire', expanded=False):
                        st.write(f"Résultats du marché, récent → ancien : {' · '.join(map(str, p['recent_values']))}")
                        defense_info = p.get('opponent_defense')
                        if defense_info:
                            st.write(f"{p['opponent']} : {defense_info['goals_against_avg']:.2f} buts encaissés / match sur {defense_info['games']} matchs terminés récents")
                            st.caption('Indicateur défensif collectif descriptif : ne mesure pas les points accordés à un joueur et ne modifie pas la probabilité estimée.')
                        else:
                            st.caption('Données défensives adverses indisponibles.')
            chosen = [p for p, key in zip(picks, selected_keys)
                      if st.session_state.get(key, False)]
            st.caption(f'{len(chosen)} pick(s) sélectionné(s) sur {len(picks)}')
            if st.button(f'Confirmer mes {len(chosen)} picks · {name}',
                         key=f'picks20_confirm_{name}', disabled=not chosen):
                added, duplicates, failures = 0, 0, 0
                for p in chosen:
                    try:
                        if follow(f'NHL Picks V20 | {name}', [p]):
                            added += 1
                        else:
                            duplicates += 1
                    except Exception as exc:
                        failures += 1
                        st.error(f"{p['selection']} : {type(exc).__name__}")
                if added:
                    st.success(f'{added} pick(s) enregistré(s) pour le suivi.')
                    st.cache_data.clear()
                if duplicates:
                    st.info(f'{duplicates} pick(s) déjà suivis, non dupliqués.')
                if failures:
                    st.warning(f'{failures} enregistrement(s) échoué(s).')
    if not past.empty:
        st.subheader('Historique détaillé')
        profile = st.selectbox('Profil historique',PROFILES,key='picks20_hist_profile')
        selected=past[past.profile==f'NHL Picks V20 | {profile}']
        if not selected.empty:
            display = selected[['created_at','selection','probability','status','kickoff']].copy()
            display['probability'] = display['probability'].map(lambda v: pct_label(float(v)) if pd.notna(v) else '—')
            for column in ('kickoff', 'created_at'):
                display[column] = pd.to_datetime(display[column], utc=True, errors='coerce').dt.tz_convert(PARIS).dt.strftime('%d/%m/%Y · %Hh%M')
            display['status'] = display['status'].map(STATUSES).fillna(display['status'])
            display = display.rename(columns={'created_at':'Créé (Paris)','selection':'Sélection','probability':'Estimation','status':'Statut','kickoff':'Match (Paris)'})
            status_filter = st.selectbox('Résultat historique', ['Tous', 'Gagné', 'Perdu', 'En attente', 'Annulé'], key='picks24_history_status')
            if status_filter != 'Tous':
                display = display[display['Statut'] == status_filter]
            st.caption(f'{len(display)} ligne(s) affichée(s) · historique de mes picks suivis, distinct des prédictions automatiques V21')
            st.dataframe(display, hide_index=True,width='stretch')
        else:
            st.info('Pas encore de pick suivi pour ce profil.')
