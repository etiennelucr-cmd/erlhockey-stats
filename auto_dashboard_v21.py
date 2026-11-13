"""Automatic versus user-followed NHL picks: independent denominators."""
import pandas as pd
import streamlit as st
from nhl_picks_v20 import PROFILES
from tracker_v14 import connect
from ui_format_v22 import audit_view
from auto_performance_v23 import certified_mask, summary as auto_summary


def show():
    st.subheader('🤖 Prédictions automatiques · Bilan et suivi')
    st.caption('Version du bilan : V25.1 · couleurs visibles + bilan V24.1')
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
    mask = certified_mask(auto)
    certified = auto[mask].copy()
    historical = auto[~mask].copy()
    a,b,c,d = st.columns(4)
    a.metric('Picks auto · tous',len(auto))
    b.metric('Auto certifiés',len(certified))
    c.metric('Auto historiques',len(historical))
    d.metric('Mes choix',len(chosen))
    if len(historical):
        st.info(f'{len(historical)} pick(s) historiques non certifiés : inclus dans le bilan automatique global, séparés du bilan certifié.')
    result=[]
    for profile in PROFILES:
        for label, frame in [('Automatique (tous)',auto),('Automatique certifié',certified),
                             ('Automatique historique',historical),('Mes choix',chosen)]:
            result.extend(auto_summary(frame,[profile],label).drop(columns=['Réussite (%)']).to_dict('records'))
    # V25.1: render a semantic HTML table. Streamlit's dataframe canvas may
    # ignore Pandas Styler row background styles in some versions/themes.
    from html import escape
    palette = {
        'Automatique (tous)': ('#142e4c', '#94caff'),
        'Automatique certifié': ('#12382f', '#81e8bb'),
        'Automatique historique': ('#3d301c', '#ffd28b'),
        'Mes choix': ('#322344', '#e1bdff'),
    }
    st.caption('🔵 Automatique (tous)  ·  🟢 Certifié  ·  🟠 Historique  ·  🟣 Mes choix')
    result_df = pd.DataFrame(result)
    headers = ''.join(f'<th>{escape(str(col))}</th>' for col in result_df.columns)
    lines = []
    for _, row in result_df.iterrows():
        bg, fg = palette.get(str(row['Origine']), ('#161616', '#f5f5f5'))
        cells = []
        for col, val in row.items():
            cell = escape(str(val)) if pd.notna(val) else '—'
            if col == 'Origine':
                cell = f'<strong style="color:{fg}">{cell}</strong>'
            elif col == 'Gagnés':
                cell = f'<span style="color:#8be2b3">{cell}</span>'
            elif col == 'Perdus':
                cell = f'<span style="color:#ff9999">{cell}</span>'
            cells.append(f'<td>{cell}</td>')
        lines.append(f'<tr style="background-color:{bg}">' + ''.join(cells) + '</tr>')
    table_html = (
        '<div class="eh-v251-table" style="overflow:auto;max-height:520px;border:1px solid #355979;border-radius:12px">'
        '<table style="border-collapse:collapse;width:100%;min-width:760px;color:#f4f6fa;font-size:13px">'
        '<thead style="position:sticky;top:0;background:#25282d;z-index:1"><tr>' + headers + '</tr></thead>'
        '<tbody>' + ''.join(lines) + '</tbody></table></div>'
        '<style>.eh-v251-table th,.eh-v251-table td{padding:9px 11px;text-align:left;'
        'border-bottom:1px solid #42505d;white-space:nowrap}'
        '.eh-v251-table th{font-weight:600;color:#e5e8ec}'
        '.eh-v251-table tr:hover{filter:brightness(1.18)}</style>'
    )
    st.markdown(table_html, unsafe_allow_html=True)

    with st.expander('🔎 Diagnostic du bilan V25.1'):
        st.caption('Les picks automatiques historiques sont comptés dans le total global, sans certification rétroactive.')
        st.write('Statuts de validation :')
        st.dataframe(auto['validation_state'].fillna('(vide)').value_counts().rename_axis('Statut').reset_index(name='Nombre'),hide_index=True)
        st.write('Statuts des résultats :')
        st.dataframe(auto['status'].fillna('(vide)').value_counts().rename_axis('Résultat').reset_index(name='Nombre'),hide_index=True)
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
        st.caption('Les anciens picks comptent dans le bilan automatique global, mais pas dans le bilan certifié. Aucun statut historique n’est modifié.')
