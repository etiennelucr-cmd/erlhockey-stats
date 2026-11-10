"""Automatic versus user-followed NHL picks: independent denominators."""
import pandas as pd
import streamlit as st
from nhl_picks_v20 import PROFILES
from tracker_v14 import connect


def show():
    st.subheader('🤖 V21 · Prédictions automatiques vs mes choix')
    st.caption('Les prédictions automatiques sont figées avant le match, même si tu ne les coches pas. '
               'Les choix personnels sont comptés séparément. Les taux excluent les matchs en attente et les annulations.')
    try:
        with connect() as conn:
            auto = pd.read_sql_query('SELECT profile,selection,probability,status,kickoff,created_at FROM v21_auto_picks',conn)
            chosen = pd.read_sql_query('''SELECT c.profile,l.selection,l.probability,l.status,l.kickoff,c.created_at
                FROM tracked_combos c JOIN tracked_legs l ON l.combo_id=c.id
                WHERE c.profile LIKE 'NHL Picks V20 | %%' ''',conn)
    except Exception as exc:
        st.warning('Bilan V21 indisponible : exécute v21_auto_picks.sql dans Supabase et vérifie la connexion.')
        st.caption(type(exc).__name__)
        return
    if not chosen.empty:
        chosen['profile'] = chosen['profile'].str.replace('NHL Picks V20 | ', '', regex=False)
    period = st.selectbox('Période V21', ['Tout','7 jours','30 jours','90 jours','365 jours'], key='v21_period')
    days = {'7 jours':7,'30 jours':30,'90 jours':90,'365 jours':365}.get(period)
    if days:
        cutoff = pd.Timestamp.now(tz='UTC')-pd.Timedelta(days=days)
        for df in (auto,chosen):
            if not df.empty:
                df['created_at'] = pd.to_datetime(df['created_at'],utc=True)
                df.drop(df[df.created_at < cutoff].index,inplace=True)
    result=[]
    for profile in PROFILES:
        for source,frame in [('Automatique',auto),('Mes choix',chosen)]:
            subset=frame[frame.profile==profile] if not frame.empty else frame
            won=int((subset.status=='won').sum()) if not subset.empty else 0
            lost=int((subset.status=='lost').sum()) if not subset.empty else 0
            result.append({'Profil':profile,'Origine':source,'Total':len(subset),'Gagnés':won,'Perdus':lost,
                           'En attente':int((subset.status=='pending').sum()) if not subset.empty else 0,
                           'Annulés':int((subset.status=='void').sum()) if not subset.empty else 0,
                           'Réussite':f'{won/(won+lost):.1%}' if won+lost else '—'})
    st.dataframe(pd.DataFrame(result),hide_index=True,use_container_width=True)
    st.caption('Une prédiction automatique est enregistrée une fois par profil et par match. '
               'Le taux de réussite ne mesure pas la rentabilité : aucune cote ni mise n’est enregistrée.')
    if not auto.empty:
        st.subheader('Historique des prédictions automatiques')
        profile=st.selectbox('Profil automatique',PROFILES,key='v21_auto_profile')
        st.dataframe(auto[auto.profile==profile].sort_values('kickoff',ascending=False),hide_index=True,use_container_width=True)
