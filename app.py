"""ErlHockey Stats V1 — interface NHL en lecture seule, sans secrets requis."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import streamlit as st

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
    st.caption("NHL • Stats V1")
    page=st.radio("Navigation", ["🏠 Tableau de bord","🥅 Buts 3 sur 5","⭐ Points 24 h","🔥 Points 5/5",
                                 "🎯 Buts 5/5","📈 Séries 24 h","👤 Statistiques joueurs","📅 Matchs NHL","📊 Historique","🔔 Alertes Telegram"])
    if st.button("🔄 Rafraîchir les données", use_container_width=True):
        get_json.clear(); leaders.clear(); game_log.clear(); st.rerun()
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
        st.info("V1 : les pages affichent les données NHL disponibles. L'historique permanent et la collecte 24 h/24 seront ajoutés ensuite.")
    elif page in ("🥅 Buts 3 sur 5","🔥 Points 5/5","🎯 Buts 5/5","📈 Séries 24 h"):
        st.caption("Analyse des joueurs présents dans les listes de leaders NHL, pas de l'ensemble des joueurs de la ligue.")
        with st.spinner("Analyse des cinq derniers matchs des joueurs sélectionnés…"):
            rows=[]
            for p in candidates():
                try:
                    s=five_game_stats(p)
                    if s: rows.append(s)
                except (requests.RequestException, ValueError, KeyError): continue
        if page=="🥅 Buts 3 sur 5": rows=[r for r in rows if r["Buts (5 matchs)"]>=3]
        elif page=="🔥 Points 5/5": rows=[r for r in rows if r["Matchs avec point"]==5]
        elif page=="🎯 Buts 5/5": rows=[r for r in rows if r["Matchs avec but"]==5]
        else:
            st.warning("V1 : série de points affichée ; le filtre 'match dans les prochaines 24 h' sera ajouté avec la collecte planifiée.")
            rows=[r for r in rows if r["Matchs avec point"]>=3]
        rows.sort(key=lambda r:(r["Points (5 matchs)"],r["Buts (5 matchs)"]),reverse=True)
        show_table(rows,["Joueur","Équipe","Buts (5 matchs)","Points (5 matchs)","Matchs avec point","Matchs avec but"])
    elif page=="⭐ Points 24 h":
        st.caption("Joueurs ayant inscrit au moins 2 points dans un match terminé sur les dernières 24 heures (heure de fin approximée par la date du match).")
        st.warning("V1 : le filtrage repose sur la date des matchs, pas sur leur heure de fin exacte.")
        with st.spinner("Analyse des matchs récents…"):
            recent=[]
            for p in candidates():
                try:
                    for g in game_log(p["id"])[:3]:
                        if g.get("gameDate","") in {today.isoformat(),(today-timedelta(days=1)).isoformat()}:
                            pts=int(g.get("goals") or 0)+int(g.get("assists") or 0)
                            if pts>=2: recent.append({"Joueur":player_name(p),"Équipe":p.get("teamAbbrev",""),"Date":g.get("gameDate"),"Points":pts,"Buts":g.get("goals",0),"Passes":g.get("assists",0)})
                except (requests.RequestException, ValueError): continue
        show_table(sorted(recent,key=lambda r:r["Points"],reverse=True))
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
        st.info("Cette rubrique sera activée lors de la connexion à Supabase. Elle conservera les statistiques passées et l'évolution des séries.")
    elif page=="🔔 Alertes Telegram":
        st.info("Connexion au bot Telegram prévue après la mise en place de la collecte permanente. Aucun message n'est envoyé depuis cette V1.")
except requests.RequestException as e:
    st.error("Impossible de récupérer les données NHL pour le moment. Réessaie avec « Rafraîchir les données ».")
    st.caption(f"Détail technique : {type(e).__name__}")
except Exception as e:
    st.error("Une erreur s'est produite pendant l'analyse des données NHL.")
    st.caption(f"Détail technique : {type(e).__name__}: {e}")

st.divider()
st.caption("ErlHockey Stats V1 • Prototype NHL • Pas de surveillance 24 h/24 à ce stade")
