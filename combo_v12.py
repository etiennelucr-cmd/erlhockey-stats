"""ErlHockey V12 combo explorer. Research estimates, not betting advice."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from itertools import combinations
import math
import pandas as pd
import streamlit as st
from tracker_v14 import follow

PARIS = ZoneInfo('Europe/Paris')
FINISHED = ('OFF', 'FINAL')


def streak(values, threshold=1):
    """Values ordered newest first. Missing values break the streak."""
    count = 0
    for value in values:
        if pd.isna(value) or float(value) < threshold:
            break
        count += 1
    return count


def smoothed_probability(values, threshold):
    """Beta(1,1) posterior mean; uncalibrated exploratory baseline."""
    if not values:
        return None
    return (1 + sum(float(v) >= threshold for v in values)) / (len(values) + 2)


def poisson_over(expected, threshold):
    n = math.floor(threshold) + 1
    return max(0., min(1., 1 - sum(math.exp(-expected) * expected**k / math.factorial(k) for k in range(n))))


def fixtures(db_query, now=None):
    now = now or datetime.now(PARIS)
    # Two Paris calendar dates, with a future-only cutoff.
    end = datetime.combine(now.date() + timedelta(days=2), datetime.min.time(), PARIS)
    df = db_query('''SELECT game_id, start_time_utc, home_team, away_team, game_state
                     FROM nhl_games WHERE start_time_utc >= %s AND start_time_utc < %s
                     AND game_state NOT IN ('OFF','FINAL','LIVE','CRIT')
                     ORDER BY start_time_utc, game_id''', (now.astimezone(timezone.utc), end.astimezone(timezone.utc)))
    if df.empty:
        return df
    df['start_paris'] = pd.to_datetime(df.start_time_utc, utc=True).dt.tz_convert(PARIS)
    return df


def player_candidates(db_query, upcoming, window=10):
    if upcoming.empty:
        return []
    teams = sorted(set(upcoming.home_team) | set(upcoming.away_team))
    df = db_query('''WITH ranked AS (
        SELECT p.player_id, p.player_name, p.team, p.game_id, p.game_date, p.goals, p.points,
        ROW_NUMBER() OVER (PARTITION BY p.player_id ORDER BY p.game_date DESC, p.game_id DESC) rn
        FROM nhl_player_games p JOIN nhl_games g ON p.game_id=g.game_id
        WHERE g.game_state IN ('OFF','FINAL') AND p.goals IS NOT NULL AND p.points IS NOT NULL
    ) SELECT * FROM ranked WHERE rn <= %s ORDER BY player_id, rn''', (max(20, window),))
    if df.empty:
        return []
    latest = df[df.rn == 1]
    roster = latest[latest.team.isin(teams)]
    picks = []
    for row in roster.itertuples():
        history = df[df.player_id == row.player_id].sort_values('rn').head(window)
        if len(history) < window:
            continue
        goals = history.goals.astype(float).tolist()
        points = history.points.astype(float).tolist()
        for game in upcoming.itertuples():
            if row.team not in (game.home_team, game.away_team):
                continue
            for label, values, target in [('1+ point', points, 1), ('2+ points', points, 2), ('1+ but', goals, 1)]:
                p = smoothed_probability(values, target)
                picks.append(dict(game_id=game.game_id, match=f'{game.away_team} @ {game.home_team}',
                                  time=game.start_paris, selection=f'{row.player_name} — {label}',
                                  market='points' if 'point' in label else 'goals', probability=p,
                                  streak=streak(values, target), hits=sum(v>=target for v in values), sample=len(values),
                                  detail=f'{sum(v>=target for v in values)}/{len(values)} matchs, streak {streak(values,target)}',
                                  caveat='Participation du joueur non confirmée'))
    return picks



def regulation_probabilities(home, away):
    """Poisson approximation for regulation-time results, including ties."""
    def probabilities(lam):
        out=[math.exp(-lam)]
        for k in range(1,19): out.append(out[-1]*lam/k)
        return out
    h,a=probabilities(home),probabilities(away)
    win=sum(x*sum(a[:i]) for i,x in enumerate(h))
    loss=sum(x*sum(h[:i]) for i,x in enumerate(a))
    tie=sum(x*y for x,y in zip(h,a))
    z=win+loss+tie
    return win/z,tie/z,loss/z

def match_candidates(db_query, upcoming, window=10):
    if upcoming.empty:
        return []
    df = db_query('''WITH results AS (
        SELECT game_id, game_date, home_team AS team, home_score AS gf, away_score AS ga
        FROM nhl_games WHERE game_state IN ('OFF','FINAL') AND home_score IS NOT NULL AND away_score IS NOT NULL
        UNION ALL
        SELECT game_id, game_date, away_team, away_score, home_score
        FROM nhl_games WHERE game_state IN ('OFF','FINAL') AND home_score IS NOT NULL AND away_score IS NOT NULL
    ), ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY team ORDER BY game_date DESC, game_id DESC) rn FROM results)
    SELECT * FROM ranked WHERE rn <= %s''', (window,))
    picks=[]
    for game in upcoming.itertuples():
        h=df[df.team == game.home_team]
        a=df[df.team == game.away_team]
        if len(h)<window or len(a)<window:
            continue
        lam_h=max(.05, (h.gf.mean()+a.ga.mean())/2)
        lam_a=max(.05, (a.gf.mean()+h.ga.mean())/2)
        total=lam_h+lam_a
        for label, probability in zip(('Domicile (60 min)', 'Nul (60 min)', 'Extérieur (60 min)'), regulation_probabilities(lam_h,lam_a)):
            picks.append(dict(game_id=game.game_id, match=f'{game.away_team} @ {game.home_team}',
                              time=game.start_paris, selection=label, market='matches',
                              probability=probability, streak=None, hits=None, sample=window,
                              detail=f'Buts attendus : {lam_h:.2f} / {lam_a:.2f}',
                              caveat='Poisson simplifié, 60 min uniquement ; gardiens et absences non pris en compte'))
        for line in (4.5,5.5,6.5):
            over=poisson_over(total,line)
            for side,p in [('Plus',over),('Moins',1-over)]:
                picks.append(dict(game_id=game.game_id, match=f'{game.away_team} @ {game.home_team}',
                                  time=game.start_paris, selection=f'{side} de {str(line).replace(".",",")} buts',
                                  market='matches', probability=p, streak=None, hits=None, sample=window,
                                  detail=f'Total attendu {total:.2f} (Poisson exploratoire)',
                                  caveat='Gardiens et absences non intégrés'))
    return picks


PROFILES = {
    'Prudent': {'range': (0.72, 1.0), 'target': 0.85, 'description': 'Priorité aux estimations élevées ; jamais sans risque.'},
    'Modéré': {'range': (0.62, 0.82), 'target': 0.73, 'description': 'Sélections à probabilité intermédiaire-haute.'},
    'Équilibré': {'range': (0.50, 0.72), 'target': 0.62, 'description': 'Diversifie les niveaux de probabilité.'},
    'Risqué': {'range': (0.35, 0.60), 'target': 0.48, 'description': 'Sélections moins probables, sans cotes vérifiées.'},
    'Ultra risqué': {'range': (0.15, 0.45), 'target': 0.30, 'description': 'Probabilité faible de réussite : scénario très spéculatif.'},
}


def build_combos(picks, legs=4, top_n=3, profile='Équilibré', diversify=False):
    """Construct combinations from distinct fixtures using profile probability bands.

    No claim of 'safety' or positive expected value: estimates are uncalibrated.
    """
    if not isinstance(legs, int) or legs < 2:
        raise ValueError('Le nombre de sélections doit être au moins 2')
    if profile not in PROFILES:
        raise ValueError('Profil inconnu')
    config = PROFILES[profile]
    low, high = config['range']
    by_game = {}
    for pick in picks:
        p = pick.get('probability')
        if p is None or not math.isfinite(p) or not low <= p <= high:
            continue
        by_game.setdefault(pick['game_id'], []).append(pick)
    if len(by_game) < legs:
        return []
    # One candidate per match per profile. Ranking near the target avoids
    # every profile returning the same highest-probability selections.
    best = [min(rows, key=lambda x: (abs(x['probability'] - config['target']),
                                      -x['probability'], x['selection']))
            for rows in by_game.values()]
    best.sort(key=lambda x: (abs(x['probability'] - config['target']), str(x['game_id'])))
    # Cap fixture pool to avoid enumerating huge combinations.
    best = best[:18]
    results = []
    for combo in combinations(best, legs):
        probability = math.prod(x['probability'] for x in combo)
        score = sum(abs(x['probability'] - config['target']) for x in combo)
        results.append((score, -probability, tuple(sorted(combo, key=lambda x: x['time']))))
    if diversify:
        results.sort(key=lambda x: (-len({p['market'] for p in x[2]}), x[0], x[1]))
    else:
        results.sort(key=lambda x: (x[0], x[1]))
    return [(-neg_prob, combo) for _, neg_prob, combo in results[:top_n]]


def show(db_query):
    st.caption('Nombre de sélections personnalisable • une seule sélection par match • ce soir et demain (heure de Paris). Estimations exploratoires non calibrées.')
    window = st.select_slider('Historique utilisé', options=[5, 10, 20], value=10, key='combo_window')
    now = datetime.now(PARIS)
    upcoming = fixtures(db_query, now)
    if upcoming.empty:
        st.warning('Aucun match à venir trouvé dans Supabase pour les deux dates civiles de Paris. Vérifie la synchronisation du calendrier.')
        return
    st.dataframe(upcoming.assign(**{'Heure (Paris)': upcoming.start_paris.dt.strftime('%d/%m %H:%M'),
                                   'Match': upcoming.away_team + ' @ ' + upcoming.home_team})[['Heure (Paris)', 'Match']],
                 hide_index=True, use_container_width=True)
    picks = player_candidates(db_query, upcoming, window) + match_candidates(db_query, upcoming, window)
    fixture_count = upcoming['game_id'].nunique()
    st.caption(f'{fixture_count} match(s) au calendrier pour la période sélectionnée.')
    if fixture_count < 2:
        st.warning('Il faut au moins deux matchs distincts pour construire un combiné.')
        return
    legs = st.select_slider('Nombre de sélections par combiné', options=list(range(2, fixture_count + 1)), value=min(4, fixture_count), key='combo_legs')
    st.caption(f'{legs} sélections sur {legs} matchs différents (maximum {fixture_count} matchs programmés).')
    st.info('Tirs cadrés indisponibles sans collecte de données. Vainqueurs en temps réglementaire estimés avec un modèle Poisson simplifié. Les absences et les gardiens ne sont pas intégrés.')
    if not picks:
        st.warning('Historique insuffisant pour produire des sélections.')
        return
    display = pd.DataFrame(picks)
    display['Probabilité exploratoire'] = display.probability.map(lambda p: f'{p:.1%}')
    with st.expander('Voir toutes les sélections analysées'):
        st.dataframe(display[['match', 'selection', 'Probabilité exploratoire', 'detail', 'caveat']].rename(
            columns={'match': 'Match', 'selection': 'Sélection', 'detail': 'Historique', 'caveat': 'Limite'}),
            hide_index=True, use_container_width=True)
    st.subheader('🧩 Les 5 profils du Combo Builder')
    st.caption('« Prudent » signifie uniquement des probabilités estimées plus élevées, pas un pari sûr. Aucun profil ne garantit un gain.')
    adaptive = st.checkbox('Adapter automatiquement le nombre de sélections si un profil manque de matchs éligibles', value=False, key='combo_adaptive')
    diversify = st.checkbox('Diversifier les marchés lorsque possible (joueurs et matchs)', value=True, key='combo_diversify')
    tabs = st.tabs([f'{name}' for name in PROFILES])
    for tab, (name, config) in zip(tabs, PROFILES.items()):
        with tab:
            low, high = config['range']
            st.caption(f"{config['description']} Plage cible par sélection : {low:.0%}–{high:.0%}.")
            available = len({p['game_id'] for p in picks if low <= p['probability'] <= high})
            actual_legs = min(legs, available) if adaptive else legs
            if actual_legs < legs and actual_legs >= 2:
                st.info(f'Profil {name} : {actual_legs} sélections au lieu de {legs}, car seulement {available} matchs sont éligibles.')
            combos = build_combos(picks, legs=actual_legs if actual_legs >= 2 else legs, top_n=3, profile=name, diversify=diversify)
            if not combos:
                st.warning(f'Pas de combiné {name.lower()} disponible : seulement {available} matchs distincts ont une sélection dans cette plage (minimum {2 if adaptive else legs}).')
                continue
            for rank, (prob, combo) in enumerate(combos, 1):
                with st.expander(f'Combo {rank} — probabilité théorique {prob:.1%}', expanded=rank == 1):
                    st.dataframe(pd.DataFrame([{
                        'Heure (Paris)': p['time'].strftime('%d/%m %H:%M'),
                        'Match': p['match'], 'Sélection': p['selection'],
                        'Estimation': f"{p['probability']:.1%}", 'Historique': p['detail']
                    } for p in combo]), hide_index=True, use_container_width=True)
                    st.caption(f'Cote juste théorique : {1/prob:.2f}. Produit de probabilités sous hypothèse d’indépendance. Pas une cote bookmaker ni une recommandation de mise.')
                    if st.button('☑️ Suivre ce combiné', key=f'track_{name}_{rank}_{"_".join(str(p["game_id"]) for p in combo)}'):
                        try:
                            inserted=follow(name,combo)
                            st.success('Combiné enregistré avant les matchs.' if inserted else 'Ce combiné est déjà suivi.')
                        except ValueError as exc:
                            st.warning(str(exc))
                        except Exception:
                            st.error('Enregistrement impossible : vérifie le schéma SQL V14 et la connexion Supabase.')
    st.caption('Ces profils ne mesurent pas la rentabilité : sans cotes et sans backtest, aucune value n’est démontrée. Les streaks peuvent s’interrompre et les joueurs être absents.')
