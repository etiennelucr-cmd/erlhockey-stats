"""ErlHockey Stats V8 — statistiques, picks et tendances NHL."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import streamlit as st
import psycopg

st.set_page_config(page_title="ErlHockey Stats", page_icon="🏒", layout="wide")
API = "https://api-web.nhle.com/v1"
PARIS = ZoneInfo("Europe/Paris")

st.markdown("""<style>
.block-container{padding-top:1.3rem;max-width:1400px}
[data-testid="stMetric"]{background:#13273b;border:1px solid #27435b;border-radius:14px;padding:14px}
h1,h2,h3{letter-spacing:-.02em}
</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=180, show_spinner=False)
def get_json(path):
    response = requests.get(f"{API}/{path}", timeout=15, headers={"User-Agent":"ErlHockeyStats/1.0"})
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=600, show_spinner=False)
def leaders(category="points", limit=100):
    data = get_json(f"skater-stats-leaders/current?categories={category}&limit={limit}")
    return data.get(category, [])

@st.cache_data(ttl=600, show_spinner=False)
def game_log(player_id):
    data = get_json(f"player/{player_id}/game-log/now")
    games = data.get("gameLog", [])
    return sorted([g for g in games if g.get("gameType", 2) == 2], key=lambda g:g.get("gameDate", ""), reverse=True)

@st.cache_data(ttl=300, show_spinner=False)
def db_query(sql, params=()):
    url = st.secrets.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("Secret SUPABASE_DB_URL absent")
    with psycopg.connect(url, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])

def db_status():
    return db_query("SELECT source, last_success_at, details FROM nhl_sync_status ORDER BY last_success_at DESC LIMIT 1")

@st.cache_data(ttl=300, show_spinner=False)
def goals_three_of_five():
    """Cinq derniers matchs terminés enregistrés par joueur, sur la fenêtre collectée."""
    return db_query("""
        WITH ranked AS (
            SELECT p.player_id, p.player_name, p.team, p.game_date,
                   p.game_id, p.goals, p.assists, p.points,
                   ROW_NUMBER() OVER (
                       PARTITION BY p.player_id
                       ORDER BY p.game_date DESC, p.game_id DESC
                   ) AS rang
            FROM nhl_player_games p
            JOIN nhl_games g ON g.game_id = p.game_id
            WHERE g.game_state IN ('OFF', 'FINAL')
        ), last_five AS (
            SELECT * FROM ranked WHERE rang <= 5
        )
        SELECT player_id, MAX(player_name) AS joueur,
               (ARRAY_AGG(team ORDER BY rang))[1] AS equipe,
               COUNT(*) AS matchs_analyses,
               COUNT(*) FILTER (WHERE goals > 0) AS matchs_avec_but,
               SUM(goals) AS buts_total,
               SUM(points) AS points_total,
               STRING_AGG(goals::text, ' - ' ORDER BY rang) AS buts_par_match
        FROM last_five
        GROUP BY player_id
        HAVING COUNT(*) = 5 AND COUNT(*) FILTER (WHERE goals > 0) >= 3
        ORDER BY matchs_avec_but DESC, buts_total DESC, points_total DESC, joueur
    """)

@st.cache_data(ttl=300, show_spinner=False)
def perfect_five_streaks(statistic):
    """Joueurs avec un but ou un point dans chacun des cinq derniers matchs terminés."""
    if statistic not in ("goals", "points"):
        raise ValueError("Statistique inconnue")
    return db_query(f"""
        WITH ranked AS (
            SELECT p.player_id, p.player_name, p.team, p.game_date,
                   p.game_id, p.goals, p.points,
                   ROW_NUMBER() OVER (
                       PARTITION BY p.player_id
                       ORDER BY p.game_date DESC, p.game_id DESC
                   ) AS rang
            FROM nhl_player_games p
            JOIN nhl_games g ON g.game_id = p.game_id
            WHERE g.game_state IN ('OFF', 'FINAL')
        )
        SELECT player_id, MAX(player_name) AS joueur,
               (ARRAY_AGG(team ORDER BY rang))[1] AS equipe,
               COUNT(*) AS matchs_analyses,
               SUM(goals) AS buts_total,
               SUM(points) AS points_total,
               STRING_AGG({statistic}::text, ' - ' ORDER BY rang) AS serie_par_match
        FROM ranked
        WHERE rang <= 5
        GROUP BY player_id
        HAVING COUNT(*) = 5 AND COUNT(*) FILTER (WHERE {statistic} > 0) = 5
        ORDER BY points_total DESC, buts_total DESC, joueur
    """)

@st.cache_data(ttl=300, show_spinner=False)
def recent_player_form():
    """Les cinq derniers matchs terminés par joueur, toutes équipes confondues."""
    return db_query("""
        WITH ranked AS (
            SELECT p.player_id, p.player_name, p.team, p.points, p.goals,
                   ROW_NUMBER() OVER (PARTITION BY p.player_id
                       ORDER BY p.game_date DESC, p.game_id DESC) AS rn
            FROM nhl_player_games p
            JOIN nhl_games g ON g.game_id = p.game_id
            WHERE g.game_state IN ('OFF','FINAL')
        )
        SELECT player_id, MAX(player_name) AS joueur,
               (ARRAY_AGG(team ORDER BY rn))[1] AS equipe,
               COUNT(*) AS matchs, SUM(points) AS points_5,
               SUM(goals) AS buts_5,
               COUNT(*) FILTER (WHERE points > 0) AS matchs_avec_point,
               SUM(CASE WHEN rn <= 2 THEN points ELSE 0 END) AS points_2,
               COUNT(*) FILTER (WHERE rn <= 2 AND points > 0) AS matchs_avec_point_2,
               STRING_AGG(points::text, ' - ' ORDER BY rn) AS points_par_match
        FROM ranked WHERE rn <= 5 GROUP BY player_id
        HAVING COUNT(*) = 5
    """)

@st.cache_data(ttl=300, show_spinner=False)
def recent_team_form():
    """Dix derniers résultats par équipe, avec domicile/extérieur et buts."""
    return db_query("""
        WITH team_games AS (
            SELECT game_id, game_date, home_team AS team, 'D' AS lieu,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS win,
                   home_score AS buts_pour, away_score AS buts_contre
            FROM nhl_games WHERE game_state IN ('OFF','FINAL')
              AND home_score IS NOT NULL AND away_score IS NOT NULL
            UNION ALL
            SELECT game_id, game_date, away_team AS team, 'E' AS lieu,
                   CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS win,
                   away_score AS buts_pour, home_score AS buts_contre
            FROM nhl_games WHERE game_state IN ('OFF','FINAL')
              AND home_score IS NOT NULL AND away_score IS NOT NULL
        ), ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY team ORDER BY game_date DESC, game_id DESC) AS rn,
                ROW_NUMBER() OVER (
                PARTITION BY team, lieu ORDER BY game_date DESC, game_id DESC) AS rn_lieu
            FROM team_games
        )
        SELECT team, lieu, rn, rn_lieu, win, buts_pour, buts_contre
        FROM ranked WHERE rn <= 10 OR rn_lieu <= 5
    """)

def upcoming_games(days=2):
    result = []
    for offset in range(days):
        day = datetime.now(PARIS).date() + timedelta(days=offset)
        for g in matches_for_day(day):
            if g.get('gameState') not in ('OFF','FINAL','LIVE','CRIT'):
                result.append(g)
    return result

def game_time(g):
    try:
        return datetime.fromisoformat(g['startTimeUTC'].replace('Z', '+00:00')).astimezone(PARIS).strftime('%d/%m %H:%M')
    except (KeyError, ValueError, AttributeError):
        return '—'

def team_predictions(games):
    """Tendances descriptives de forme, non probabilités de victoire."""
    form = recent_team_form()
    rows = []

    def summary(team, lieu):
        team_rows = form[form['team'] == team]
        last5 = team_rows[team_rows['rn'] <= 5]
        last10 = team_rows[team_rows['rn'] <= 10]
        venue = team_rows[(team_rows['lieu'] == lieu) & (team_rows['rn_lieu'] <= 5)]
        if len(last5) < 5:
            return None
        w5 = int(last5['win'].sum())
        w10 = int(last10['win'].sum())
        n10 = len(last10)
        gf = int(last5['buts_pour'].sum())
        ga = int(last5['buts_contre'].sum())
        vn = len(venue)
        vw = int(venue['win'].sum())
        score = 0.55 * (w5 / 5) + 0.25 * (w10 / n10)
        score += 0.10 * max(-1, min(1, (gf - ga) / 10))
        score += 0.10 * (vw / vn) if vn >= 2 else 0.05
        return dict(score=score, w5=w5, w10=w10, n10=n10,
                    gf=gf, ga=ga, vw=vw, vn=vn)

    for g in games:
        away = g.get('awayTeam', {}).get('abbrev', '?')
        home = g.get('homeTeam', {}).get('abbrev', '?')
        a, h = summary(away, 'E'), summary(home, 'D')
        if a is None or h is None:
            favorite = 'Indéterminé'
            confidence = 'Non évaluée'
            reason = 'Moins de 5 matchs terminés pour une équipe'
            wins = '—'
            detail = '—'
        else:
            diff = h['score'] - a['score']
            gap = abs(diff)
            favorite = 'Match serré' if gap < 0.12 else (home if diff > 0 else away)
            # Seuils de lecture du score interne : ce ne sont pas des probabilités.
            if gap < 0.12:
                confidence = 'Faible'
            elif gap < 0.25:
                confidence = 'Moyenne'
            else:
                confidence = 'Forte'
            leading = home if diff > 0 else away
            leader = h if diff > 0 else a
            other = a if diff > 0 else h
            if favorite == 'Match serré':
                reason = f'Forme proche : {away} {a["w5"]}/5, {home} {h["w5"]}/5 victoires'
            else:
                reason = (f'{leading} : {leader["w5"]}/5 victoires récentes '
                          f'contre {other["w5"]}/5')
            wins = (f'{away} : {a["w5"]}/5 et {a["w10"]}/{a["n10"]} ; '
                    f'{home} : {h["w5"]}/5 et {h["w10"]}/{h["n10"]}')
            def venue_text(team, x, label):
                return (f'{team} {label} : {x["vw"]}/{x["vn"]} victoires'
                        if x['vn'] >= 2 else f'{team} {label} : données limitées')
            detail = (f'Buts sur 5 : {away} {a["gf"]}-{a["ga"]}, '
                      f'{home} {h["gf"]}-{h["ga"]} ; '
                      f'{venue_text(away, a, "extérieur")} ; '
                      f'{venue_text(home, h, "domicile")}')
        rows.append({'Heure (Paris)': game_time(g), 'Match': f'{away} @ {home}',
                     'Équipe favorite': favorite, 'Confiance statistique': confidence,
                     'Pourquoi ?': reason, 'Victoires (5 et 10 matchs)': wins,
                     'Buts et domicile/extérieur': detail})
    return rows

def player_name(p):
    def part(v): return v.get("default", "") if isinstance(v, dict) else str(v or "")
    return (part(p.get("firstName")) + " " + part(p.get("lastName"))).strip()

def candidates():
    found = {}
    for category in ("points", "goals", "assists"):
        for p in leaders(category, 100):
            if p.get("id"): found[p["id"]] = p
    return list(found.values())

def five_game_stats(p):
    games = game_log(p["id"])[:5]
    if len(games) != 5: return None
    goals = [int(g.get("goals") or 0) for g in games]
    assists = [int(g.get("assists") or 0) for g in games]
    return {"Joueur": player_name(p), "Équipe": p.get("teamAbbrev", ""), "Buts (5 matchs)":sum(goals),
            "Points (5 matchs)":sum(goals)+sum(assists), "Matchs avec point":sum(g+a>0 for g,a in zip(goals,assists)),
            "Matchs avec but":sum(g>0 for g in goals), "ID":p["id"]}

def matches_for_day(day):
    return get_json(f"score/{day.isoformat()}").get("games", [])

def matches_table(games):
    rows=[]
    for g in games:
        start=g.get("startTimeUTC")
        try: local=datetime.fromisoformat(start.replace("Z","+00:00")).astimezone(PARIS).strftime("%d/%m %H:%M") if start else "—"
        except ValueError: local="—"
        away=g.get("awayTeam",{}); home=g.get("homeTeam",{})
        rows.append({"Heure (Paris)":local,"Extérieur":away.get("abbrev","?"),"Score ext.":away.get("score","—"),
                     "Domicile":home.get("abbrev","?"),"Score dom.":home.get("score","—"),"État":g.get("gameState","?")})
    return rows

def show_table(rows, columns=None):
    if rows: st.dataframe(pd.DataFrame(rows)[columns] if columns else pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else: st.info("Aucun résultat dans l'échantillon analysé.")

with st.sidebar:
    st.title("🏒 ErlHockey")
    st.caption("NHL • Stats V8")
    page=st.radio("Navigation", ["🏠 Tableau de bord","🥅 Buts 3 sur 5","⭐ Points 24 h","🔥 Points 5/5",
                                 "🎯 Buts 5/5","🎯 NHL Picks","📈 Séries 24 h","👤 Statistiques joueurs","📅 Matchs NHL","📊 Historique","🔔 Alertes Telegram"])
    if st.button("🔄 Rafraîchir les données", use_container_width=True):
        get_json.clear(); leaders.clear(); game_log.clear(); goals_three_of_five.clear(); perfect_five_streaks.clear(); recent_player_form.clear(); recent_team_form.clear(); db_query.clear(); st.rerun()
    st.caption("Données publiques NHL. Les statistiques peuvent être différées.")

st.title(page)
st.caption("🏒 NHL • Données consultées à la demande • Heure de Paris")

try:
    today=datetime.now(PARIS).date()
    if page=="🏠 Tableau de bord":
        games=matches_for_day(today)
        completed=sum(g.get("gameState") in ("OFF","FINAL") for g in games)
        live=sum(g.get("gameState") in ("LIVE","CRIT") for g in games)
        a,b,c=st.columns(3)
        a.metric("Matchs du jour",len(games)); b.metric("Terminés",completed); c.metric("En cours",live)
        st.subheader("📅 Matchs du jour")
        show_table(matches_table(games))
        st.subheader("🔮 Prédictions — matchs du jour")
        st.caption("Tendances expérimentales fondées sur la forme récente et les buts. La confiance exprime seulement l’écart du score interne entre équipes : ce n’est pas une probabilité de victoire.")
        future = [g for g in games if g.get('gameState') not in ('OFF','FINAL','LIVE','CRIT')]
        if future:
            predictions = team_predictions(future)
            short_cols = ['Heure (Paris)', 'Match', 'Équipe favorite',
                          'Confiance statistique', 'Pourquoi ?']
            show_table([{k: row[k] for k in short_cols} for row in predictions])
            with st.expander('📊 Voir les statistiques détaillées des prédictions'):
                show_table(predictions)
        else:
            st.info("Aucun match à venir aujourd'hui à analyser.")
        st.caption("En NHL, il n'y a pas de match nul au résultat final : une égalité après 60 minutes mène à la prolongation ou aux tirs au but. La mention « match serré » n'est pas un pronostic de nul réglementaire. Gardiens, blessures et compositions non pris en compte.")
    elif page=="🥅 Buts 3 sur 5":
        st.caption("Joueurs ayant marqué au moins un but dans 3 de leurs 5 derniers matchs terminés enregistrés dans Supabase.")
        st.info("Calcul fondé sur les matchs disponibles dans l'historique collecté (fenêtre actuelle limitée). Les joueurs ayant moins de 5 matchs enregistrés sont exclus.")
        with st.spinner("Calcul des séries de buts depuis Supabase…"):
            results = goals_three_of_five()
        if results.empty:
            st.info("Aucun joueur ne répond à ce critère dans les données actuellement enregistrées.")
        else:
            st.metric("Joueurs qualifiés", len(results))
            results = results.rename(columns={
                "joueur":"Joueur", "equipe":"Équipe", "matchs_analyses":"Matchs analysés",
                "matchs_avec_but":"Matchs avec but", "buts_total":"Buts (5 matchs)",
                "points_total":"Points (5 matchs)", "buts_par_match":"Buts par match (récent → ancien)"
            })
            st.dataframe(results.drop(columns=["player_id"]), hide_index=True, use_container_width=True)
    elif page in ("🔥 Points 5/5", "🎯 Buts 5/5"):
        is_points = page == "🔥 Points 5/5"
        statistic = "points" if is_points else "goals"
        st.caption(
            "Joueurs ayant obtenu au moins un point dans chacun de leurs cinq derniers matchs terminés."
            if is_points else
            "Joueurs ayant marqué au moins un but dans chacun de leurs cinq derniers matchs terminés."
        )
        st.info("Données Supabase : cinq matchs terminés requis par joueur. Calcul sur l'historique actuellement collecté.")
        with st.spinner("Calcul des séries depuis Supabase…"):
            results = perfect_five_streaks(statistic)
        if results.empty:
            st.info("Aucun joueur ne répond actuellement à ce critère dans les données enregistrées.")
        else:
            st.metric("Joueurs qualifiés", len(results))
            results = results.rename(columns={
                "joueur": "Joueur", "equipe": "Équipe",
                "matchs_analyses": "Matchs analysés",
                "buts_total": "Buts (5 matchs)",
                "points_total": "Points (5 matchs)",
                "serie_par_match": ("Points par match (récent → ancien)" if is_points
                                    else "Buts par match (récent → ancien)")
            })
            st.dataframe(results.drop(columns=["player_id"]), hide_index=True, use_container_width=True)
    elif page=="📈 Séries 24 h":
        st.caption("Joueurs ayant obtenu un point dans au moins 3 de leurs 5 derniers matchs et dont l'équipe joue dans les 24 prochaines heures.")
        st.info("Fenêtre glissante de 24 heures calculée à partir des horaires officiels de début des matchs NHL (heure de Paris). Seuls les matchs non commencés sont retenus.")
        minimum = st.selectbox("Régularité minimale", [3, 4, 5], index=0,
                               format_func=lambda n: f"{n}/5 matchs avec point")
        now_utc = datetime.now(timezone.utc)
        deadline_utc = now_utc + timedelta(hours=24)
        # Consulter aussi le surlendemain pour couvrir les 24 heures autour de minuit.
        upcoming_24h = []
        seen_games = set()
        for offset in range(3):
            day = datetime.now(PARIS).date() + timedelta(days=offset)
            for g in matches_for_day(day):
                if g.get("gameState") in ("OFF", "FINAL", "LIVE", "CRIT"):
                    continue
                try:
                    start_utc = datetime.fromisoformat(g["startTimeUTC"].replace("Z", "+00:00"))
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
                if not now_utc <= start_utc < deadline_utc:
                    continue
                game_key = g.get("id") or (g.get("startTimeUTC"),
                    g.get("awayTeam", {}).get("abbrev"), g.get("homeTeam", {}).get("abbrev"))
                if game_key in seen_games:
                    continue
                seen_games.add(game_key)
                upcoming_24h.append((start_utc, g))
        upcoming_24h.sort(key=lambda item: item[0])
        if not upcoming_24h:
            st.info("Aucun match NHL non commencé dans les prochaines 24 heures.")
        else:
            with st.spinner("Recherche des séries de points dans Supabase…"):
                form = recent_player_form()
            rows = []
            seen_players = set()
            for start_utc, g in upcoming_24h:
                away = g.get("awayTeam", {}).get("abbrev", "?")
                home = g.get("homeTeam", {}).get("abbrev", "?")
                for _, player in form[form["equipe"].isin((away, home))].iterrows():
                    played = int(player["matchs_avec_point"])
                    if played < minimum:
                        continue
                    player_id = str(player["player_id"])
                    if player_id in seen_players:
                        continue
                    seen_players.add(player_id)
                    rows.append({
                        "Heure (Paris)": start_utc.astimezone(PARIS).strftime("%d/%m %H:%M"),
                        "Match": f"{away} @ {home}",
                        "Joueur": player["joueur"],
                        "Équipe": player["equipe"],
                        "Adversaire": home if player["equipe"] == away else away,
                        "Matchs avec point / 5": played,
                        "Points / 5": int(player["points_5"]),
                        "Points / 2 derniers": int(player["points_2"]),
                        "Points par match (récent → ancien)": player["points_par_match"],
                    })
            rows.sort(key=lambda r: (-r["Matchs avec point / 5"], -r["Points / 5"],
                                     -r["Points / 2 derniers"], r["Heure (Paris)"], r["Joueur"]))
            st.metric("Joueurs en série jouant sous 24 h", len(rows))
            show_table(rows)
            st.caption("Analyse fondée sur les matchs terminés collectés dans Supabase. La présence effective des joueurs et les compositions ne sont pas vérifiées.")
    elif page=="⭐ Points 24 h":
        st.caption("Joueurs avec au moins 2 points lors d'un match terminé récemment, parmi tous les joueurs enregistrés dans Supabase.")
        st.warning("Fenêtre approximative : matchs datés d'aujourd'hui ou d'hier (heure de Paris), pas une mesure exacte des 24 heures depuis la fin du match.")
        dates = (today.isoformat(), (today-timedelta(days=1)).isoformat())
        recent = db_query("""
            SELECT p.player_name AS "Joueur", p.team AS "Équipe", p.game_date AS "Date",
                   p.points AS "Points", p.goals AS "Buts", p.assists AS "Passes"
            FROM nhl_player_games p JOIN nhl_games g ON g.game_id = p.game_id
            WHERE g.game_state IN ('OFF','FINAL') AND p.points >= 2
              AND p.game_date IN (%s, %s)
            ORDER BY p.points DESC, p.game_date DESC, p.player_name
        """, dates)
        show_table(recent.to_dict('records'))
    elif page=="🎯 NHL Picks":
        st.caption("Joueurs à surveiller pour obtenir au moins un point lors de leur prochain match NHL. Un seul pick par joueur.")
        st.info("Classement expérimental fondé sur les cinq derniers matchs et la forme des deux plus récents. Ce score n'est pas une probabilité de réussite ni un conseil de pari.")
        upcoming = upcoming_games(2)
        if not upcoming:
            st.info("Aucun match programmé aujourd'hui ou demain dans les données NHL.")
        else:
            # Un match peut apparaître sur deux dates locales selon le calendrier NHL.
            unique_games = {}
            now_utc = datetime.now(timezone.utc)
            for g in upcoming:
                try:
                    start = datetime.fromisoformat(g['startTimeUTC'].replace('Z', '+00:00'))
                except (KeyError, ValueError, AttributeError):
                    continue
                if start >= now_utc:
                    unique_games[str(g.get('id') or (g.get('startTimeUTC'),
                                 g.get('awayTeam', {}).get('abbrev'),
                                 g.get('homeTeam', {}).get('abbrev')))] = g
            upcoming = sorted(unique_games.values(), key=lambda g: g.get('startTimeUTC', ''))
            if not upcoming:
                st.info("Aucun match futur dans la période analysée.")
            else:
                match_options = ['Tous les matchs'] + [
                    f"{game_time(g)} — {g.get('awayTeam', {}).get('abbrev', '?')} @ {g.get('homeTeam', {}).get('abbrev', '?')}"
                    for g in upcoming
                ]
                left, middle, right = st.columns(3)
                with left:
                    display_count = st.selectbox('Nombre de picks', [10, 20, 'Tous'], index=0)
                with middle:
                    selected_match = st.selectbox('Match à analyser', match_options)
                with right:
                    min_regular = st.selectbox('Régularité minimale', [3, 4, 5], index=0,
                                               format_func=lambda n: f'{n}/5 matchs avec point')
                selected_games = upcoming if selected_match == 'Tous les matchs' else [
                    upcoming[match_options.index(selected_match) - 1]
                ]
                form = recent_player_form()
                rows = []
                seen_players = set()
                # Les matchs sont chronologiques : conserver le prochain match de chaque joueur.
                for g in selected_games:
                    away = g.get('awayTeam', {}).get('abbrev', '?')
                    home = g.get('homeTeam', {}).get('abbrev', '?')
                    for _, p in form[form['equipe'].isin((away, home))].iterrows():
                        played = int(p['matchs_avec_point'])
                        if played < min_regular:
                            continue
                        player_key = str(p['player_id'])
                        if player_key in seen_players:
                            continue
                        seen_players.add(player_key)
                        points = int(p['points_5'])
                        recent_points = int(p['points_2'])
                        recent_games = int(p['matchs_avec_point_2'])
                        # Score heuristique : régularité dominante, puis volume et forme récente.
                        score = played * 10 + min(points, 15) * 2 + min(recent_points, 8) * 3 + recent_games * 4
                        signal = ('Fort' if played == 5 and recent_games == 2 and points >= 7
                                  else 'Modéré' if played >= 4 and recent_games >= 1
                                  else 'À surveiller')
                        rows.append({
                            'Heure (Paris)': game_time(g), 'Match': f'{away} @ {home}',
                            'Joueur': p['joueur'], 'Équipe': p['equipe'],
                            'Adversaire': home if p['equipe'] == away else away,
                            'Signal': signal, 'Score indicatif': score,
                            'Matchs avec point / 5': played, 'Points / 5': points,
                            'Points / 2 derniers': recent_points,
                            'Points par match (récent → ancien)': p['points_par_match']
                        })
                rows.sort(key=lambda r: (-r['Score indicatif'], -r['Matchs avec point / 5'],
                                         -r['Points / 5'], r['Joueur']))
                st.metric('Joueurs repérés', len(rows))
                visible = rows if display_count == 'Tous' else rows[:display_count]
                st.caption(f"{len(visible)} picks affichés sur {len(rows)} joueurs repérés. "
                           "Score = 10 × matchs avec point + 2 × points sur 5 matchs (plafond 15) "
                           "+ 3 × points sur 2 matchs (plafond 8) + 4 × matchs avec point sur 2.")
                show_table(visible)
                st.caption("Les blessures, les compositions, les gardiens et les cotes ne sont pas intégrés. "
                           "Un joueur sélectionné peut ne pas participer au match.")
    elif page=="👤 Statistiques joueurs":
        st.caption("Recherche parmi les joueurs des listes de leaders NHL ; recherche exhaustive à venir.")
        pool=candidates()
        names={f"{player_name(p)} ({p.get('teamAbbrev','')})":p for p in pool}
        q=st.text_input("Filtrer les joueurs",placeholder="Ex. McDavid")
        filtered=[n for n in names if q.casefold() in n.casefold()]
        if filtered:
            choice=st.selectbox("Choisir un joueur",filtered)
            p=names[choice]
            games=game_log(p["id"])
            st.subheader(choice)
            if games:
                st.metric("Points sur les 5 derniers matchs",sum(int(g.get("goals") or 0)+int(g.get("assists") or 0) for g in games[:5]))
                show_table([{"Date":g.get("gameDate"),"Adversaire":g.get("opponentAbbrev",""),"Buts":g.get("goals",0),"Passes":g.get("assists",0),"Points":int(g.get("goals") or 0)+int(g.get("assists") or 0)} for g in games[:30]])
            else: st.info("Aucun match de saison régulière disponible pour ce joueur.")
        else: st.info("Aucun joueur correspondant dans l'échantillon disponible.")
    elif page=="📅 Matchs NHL":
        day=st.date_input("Date des matchs",value=today)
        show_table(matches_table(matches_for_day(day)))
    elif page=="📊 Historique":
        st.caption("Données NHL conservées dans Supabase par la collecte automatique.")
        try:
            status = db_status()
            if not status.empty:
                last = status.iloc[0]["last_success_at"]
                st.info(f"Dernière collecte : {last.astimezone(PARIS):%d/%m/%Y %H:%M} (Paris) — {status.iloc[0]['details']}")
            totals = db_query("SELECT (SELECT COUNT(*) FROM nhl_games) AS matchs, (SELECT COUNT(*) FROM nhl_player_games) AS joueurs")
            a, b = st.columns(2)
            a.metric("Matchs enregistrés", int(totals.iloc[0]["matchs"]))
            b.metric("Statistiques joueurs", int(totals.iloc[0]["joueurs"]))
            st.subheader("Matchs enregistrés")
            games_db = db_query("SELECT game_date AS date, away_team AS exterieur, away_score AS score_ext, home_team AS domicile, home_score AS score_dom, game_state AS etat FROM nhl_games ORDER BY game_date DESC, game_id DESC LIMIT 250")
            show_table(games_db.to_dict("records"))
            st.subheader("Statistiques d'un joueur")
            query = st.text_input("Rechercher un joueur", placeholder="Ex. McDavid")
            if query.strip():
                stats = db_query("SELECT game_date AS date, player_name AS joueur, team AS equipe, goals AS buts, assists AS passes, points FROM nhl_player_games WHERE player_name ILIKE %s ORDER BY game_date DESC LIMIT 100", (f"%{query.strip()}%",))
                show_table(stats.to_dict("records"))
        except Exception as exc:
            st.error("Impossible de lire l'historique Supabase.")
            st.caption(f"Détail : {type(exc).__name__}: {exc}")
    elif page=="🔔 Alertes Telegram":
        st.info("Connexion au bot Telegram prévue après la mise en place de la collecte permanente. Aucun message n'est envoyé depuis cette V1.")
except requests.RequestException as e:
    st.error("Impossible de récupérer les données NHL pour le moment. Réessaie avec « Rafraîchir les données ».")
    st.caption(f"Détail technique : {type(e).__name__}")
except Exception as e:
    st.error("Une erreur s'est produite pendant l'analyse des données NHL.")
    st.caption(f"Détail technique : {type(e).__name__}: {e}")

st.divider()
st.caption("ErlHockey Stats V8 • Collecte planifiée via GitHub Actions")
