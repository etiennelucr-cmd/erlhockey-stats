"""Automatic versus user-followed NHL picks: independent denominators."""
import pandas as pd
import streamlit as st
from nhl_picks_v20 import PROFILES
from tracker_v14 import connect
from ui_format_v22 import audit_view


def show():
    st.subheader('🤖 Prédictions automatiques · Bilan et suivi')
    st.caption('Les prédictions automatiques sont figées avant le match, même si tu ne les coches pas. '
               'Les choix personnels sont comptés séparément. Les taux excluent les matchs en attente et les annulations.')
    try:
        with connect() as conn:
            auto = pd.read_sql_query('SELECT profile,selection,probability,status,kickoff,created_at,validation_state,validation_version,validation_note FROM v21_auto_picks',conn)
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
    if not auto.empty:
        legacy_count = int((~(auto.validation_state.eq('roster_verified') & auto.validation_version.notna())).sum())
        if legacy_count:
            st.warning(f'{legacy_count} ancien(s) pick(s) non certifie(s) conserves pour audit et exclus du taux automatique certifie.')
        auto_certified = auto[auto.validation_state.eq('roster_verified') & auto.validation_version.notna()].copy()
    else:
        auto_certified = auto
    result=[]
    for profile in PROFILES:
        for source,frame in [('Automatique certifie',auto_certified),('Mes choix',chosen)]:
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
        subset = auto[auto.profile==profile].sort_values('kickoff',ascending=True)
        st.dataframe(audit_view(subset),hide_index=True,width='stretch',
                     column_config={'Estimation (%)':st.column_config.ProgressColumn('Estimation (%)',min_value=0,max_value=100,format='%.1f %%')})
        with st.expander('🔎 Détails techniques de certification'):
            st.dataframe(audit_view(subset,technical=True),hide_index=True,width='stretch')
        st.caption('Les anciennes lignes non certifiees sont visibles ici pour audit, mais exclues des taux automatiques certifies.')
