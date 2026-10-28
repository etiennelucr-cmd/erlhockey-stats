"""V12: exploratory NHL player and game market analysis, not wagering advice."""
import math
import pandas as pd
import streamlit as st


def poisson_tail(lam, threshold):
    """P(X >= threshold) for nonnegative integer threshold."""
    if threshold <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(threshold))))


def player_history(db_query, limit=20):
    # Latest N completed games per player. Avoid future games and incomplete scores.
    return db_query("""
        WITH ranked AS (
          SELECT p.player_id, p.player_name, p.team, p.game_date, p.game_id,
                 p.goals, p.points,
                 ROW_NUMBER() OVER (PARTITION BY p.player_id ORDER BY p.game_date DESC, p.game_id DESC) rn
          FROM nhl_player_games p JOIN nhl_games g ON g.game_id=p.game_id
          WHERE g.game_state IN ('OFF','FINAL') AND p.goals IS NOT NULL AND p.points IS NOT NULL
        ) SELECT player_id, player_name, team, game_date, game_id, goals, points, rn
          FROM ranked WHERE rn <= %s ORDER BY player_name, rn
    """, (limit,))


def team_history(db_query, limit=20):
    return db_query("""
      WITH games AS (
        SELECT game_id, game_date, home_team AS team, home_score AS gf, away_score AS ga,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS won
          FROM nhl_games WHERE game_state IN ('OFF','FINAL') AND home_score IS NOT NULL AND away_score IS NOT NULL
        UNION ALL
        SELECT game_id, game_date, away_team, away_score, home_score,
               CASE WHEN away_score > home_score THEN 1 ELSE 0 END
          FROM nhl_games WHERE game_state IN ('OFF','FINAL') AND home_score IS NOT NULL AND away_score IS NOT NULL
      ), ranked AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY team ORDER BY game_date DESC, game_id DESC) rn FROM games
      ) SELECT * FROM ranked WHERE rn <= %s ORDER BY team, rn
    """, (limit,))


def rate(values, minimum):
    """Beta(1,1) posterior mean; intentionally simple baseline."""
    successes = sum(float(x) >= minimum for x in values)
    return (successes + 1) / (len(values) + 2)


def show(db_query):
    st.caption('V12 • Études statistiques et probabilités expérimentales. Aucun pari garanti, aucune cote ni mise conseillée.')
    tab_players, tab_games = st.tabs(['👤 Marchés joueurs', '🏟️ Marchés matchs'])
    with tab_players:
        window = st.select_slider('Derniers matchs (joueurs)', options=[5, 10, 20], value=10, key='v12_player_window')
        df = player_history(db_query)
        if df.empty:
            st.warning('Aucun historique de joueurs dans Supabase.')
        else:
            players = df.sort_values('rn').drop_duplicates('player_id')
            names = dict(zip(players.player_id, players.player_name))
            selected = st.selectbox('Joueur', players.player_id.tolist(), format_func=lambda pid: names[pid], key='v12_player')
            sample = df[df.player_id == selected].sort_values('rn').head(window)
            n = len(sample)
            if n < window:
                st.warning(f'Historique incomplet : {n} matchs disponibles sur {window}.')
            if n:
                goals = sample.goals.astype(float).tolist()
                points = sample.points.astype(float).tolist()
                a,b,c = st.columns(3)
                a.metric('Buts / match', f'{sum(goals)/n:.2f}')
                b.metric('Points / match', f'{sum(points)/n:.2f}')
                c.metric('Matchs analysés', n)
                rows=[]
                for label, vals, threshold in [('1+ but',goals,1),('1+ point',points,1),('2+ points',points,2)]:
                    hits=sum(v>=threshold for v in vals)
                    rows.append({'Marché':label,'Réussites':f'{hits}/{n}','Fréquence historique':f'{hits/n:.1%}',
                                 'Probabilité lissée (exploratoire)':f'{rate(vals,threshold):.1%}'})
                st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
                st.caption('Probabilité lissée : moyenne a posteriori Beta(1,1) des succès observés, non calibrée pour le prochain adversaire. Les tirs ne sont pas disponibles dans le schéma actuel.')
                st.dataframe(sample[['game_date','team','goals','points']].rename(columns={'game_date':'Date','team':'Équipe','goals':'Buts','points':'Points'}),hide_index=True,use_container_width=True)
    with tab_games:
        window = st.select_slider('Derniers matchs (équipes)',options=[5,10,20],value=10,key='v12_team_window')
        df=team_history(db_query)
        if df.empty:
            st.warning('Aucun historique de matchs terminés dans Supabase.')
        else:
            teams=sorted(df.team.dropna().unique().tolist())
            home=st.selectbox('Équipe à domicile',teams,key='v12_home')
            away=st.selectbox('Équipe à l’extérieur',teams,index=1 if len(teams)>1 else 0,key='v12_away')
            if home==away:
                st.info('Sélectionne deux équipes différentes.')
            else:
                h=df[df.team==home].sort_values('rn').head(window)
                a=df[df.team==away].sort_values('rn').head(window)
                if len(h)<window or len(a)<window:
                    st.warning(f'Échantillons incomplets : {home} {len(h)}/{window}, {away} {len(a)}/{window}.')
                if not h.empty and not a.empty:
                    hgf,hga=h.gf.mean(),h.ga.mean()
                    agf,aga=a.gf.mean(),a.ga.mean()
                    lam_home=max(0.05,(hgf+aga)/2)
                    lam_away=max(0.05,(agf+hga)/2)
                    total=lam_home+lam_away
                    c1,c2,c3=st.columns(3)
                    c1.metric('Buts attendus domicile',f'{lam_home:.2f}')
                    c2.metric('Buts attendus extérieur',f'{lam_away:.2f}')
                    c3.metric('Total attendu',f'{total:.2f}')
                    rows=[]
                    for line in [4.5,5.5,6.5]:
                        over=poisson_tail(total,math.floor(line)+1)
                        rows.append({'Marché':f'Plus de {str(line).replace(".",",")} buts','Estimation exploratoire':f'{over:.1%}'})
                        rows.append({'Marché':f'Moins de {str(line).replace(".",",")} buts','Estimation exploratoire':f'{1-over:.1%}'})
                    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
                    st.caption('Modèle Poisson indépendant, basé sur les buts marqués/encaissés récemment. Ce ne sont pas des probabilités calibrées. Pas de prise en compte des gardiens, blessures, adversaires rencontrés, domicile/extérieur, ni des prolongations. Les marchés vainqueur et handicap nécessitent un modèle validé et des données réglementaires adaptées.')
