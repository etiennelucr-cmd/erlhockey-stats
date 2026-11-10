"""V21.9 unified profile analytics: tracked combinations and certified auto picks."""
import pandas as pd

PROFILES = ['Prudent', 'Modéré', 'Équilibré', 'Risqué', 'Ultra risqué']


def summarize(combos, legs):
    """Count each tracked leg occurrence; unresolved and void legs excluded from rates."""
    rows = []
    for profile in PROFILES:
        c = combos[combos['profile'] == profile]
        l = legs[legs['combo_id'].isin(c['id'])]
        cw, cl = int((c['status'] == 'won').sum()), int((c['status'] == 'lost').sum())
        lw, ll = int((l['status'] == 'won').sum()), int((l['status'] == 'lost').sum())
        groups = l.groupby('combo_id')['status'].agg(list).to_dict() if not l.empty else {}
        resolved_losses = 0
        near = {}
        for statuses in groups.values():
            if not statuses or not all(s in ('won', 'lost') for s in statuses):
                continue
            if 'lost' in statuses:
                resolved_losses += 1
                if statuses.count('lost') == 1 and statuses.count('won') == len(statuses)-1:
                    key = f'{len(statuses)-1}/{len(statuses)}'
                    near[key] = near.get(key, 0) + 1
        near_count = sum(near.values())
        rows.append({'Profil': profile, 'Combinés suivis': len(c),
                     'Combinés gagnés': cw, 'Combinés perdus': cl,
                     'Combinés en attente': int((c['status'] == 'pending').sum()),
                     'À une sélection près': near_count,
                     'Presque gagnés / perdus (%)': round(100*near_count/resolved_losses,2) if resolved_losses else None,
                     'Détail presque gagnés': ', '.join(f'{k} : {v}' for k,v in sorted(near.items())) or '—',
                     'Réussite combinés (%)': round(100*cw/(cw+cl),2) if cw+cl else None,
                     'Sélections gagnées': lw, 'Sélections perdues': ll,
                     'Réussite sélections (%)': round(100*lw/(lw+ll),2) if lw+ll else None,
                     'Sélections en attente': int((l['status'] == 'pending').sum()),
                     'Sélections annulées': int((l['status'] == 'void').sum())})
    return pd.DataFrame(rows)


def auto_summary(auto):
    """Certified-only performance; legacy rows never enter denominators."""
    certified = auto[auto['validation_state'].eq('roster_verified') & auto['validation_version'].notna()].copy()
    rows = []
    for profile in PROFILES:
        subset = certified[certified['profile'] == profile]
        won = int(subset['status'].eq('won').sum())
        lost = int(subset['status'].eq('lost').sum())
        rows.append({'Profil':profile,'Certifiés':len(subset),'Gagnés':won,'Perdus':lost,
                     'En attente':int(subset['status'].eq('pending').sum()),
                     'Annulés':int(subset['status'].eq('void').sum()),
                     'Réussite (%)':round(100*won/(won+lost),2) if won+lost else None})
    return pd.DataFrame(rows), certified


def _pct(v):
    return '—' if pd.isna(v) else f'{v:.1f} %'


def show():
    import streamlit as st
    from tracker_v14 import connect
    st.markdown('''<style>
    .eh-analytics-intro{background:linear-gradient(120deg,#0d2741,#123b60);border:1px solid #28608a;
      border-radius:18px;padding:20px 24px;margin:0 0 18px}
    .eh-analytics-intro h3{color:#f5fbff;margin:0 0 6px;font-size:1.35rem}
    .eh-analytics-intro p{color:#b9d3e8;margin:0}
    div[data-testid="stMetric"]{border-radius:16px!important}
    </style>''',unsafe_allow_html=True)
    st.markdown('<div class="eh-analytics-intro"><h3>📊 Tableau de performance · 5 profils</h3>'
                '<p>Deux historiques indépendants : tes combinés personnels et les prédictions automatiques certifiées.</p></div>',
                unsafe_allow_html=True)
    period = st.selectbox('📅 Période de création', ['Tout l’historique','7 jours','30 jours','90 jours','365 jours'],key='v216_period')
    days = {'7 jours':7,'30 jours':30,'90 jours':90,'365 jours':365}.get(period)
    try:
        with connect() as conn:
            combos = pd.read_sql_query('SELECT id,profile,status,created_at FROM tracked_combos',conn)
            legs = pd.read_sql_query('SELECT combo_id,status FROM tracked_legs',conn)
            auto = pd.read_sql_query('''SELECT profile,selection,probability,status,kickoff,created_at,
                        validation_state,validation_version,validation_note FROM v21_auto_picks''',conn)
    except Exception as exc:
        st.error('Impossible de charger le bilan depuis Supabase. Vérifie la connexion et les tables tracked_combos, tracked_legs et v21_auto_picks.')
        st.caption(f'Diagnostic : {type(exc).__name__} — {exc}')
        return
    if days:
        cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=days)
        for df in (combos,auto):
            if not df.empty:
                dates = pd.to_datetime(df['created_at'],utc=True,errors='coerce')
                df.drop(df.index[dates < cutoff],inplace=True)
    summary = summarize(combos,legs)
    auto_stats, certified = auto_summary(auto)
    legacy = auto[~(auto['validation_state'].eq('roster_verified') & auto['validation_version'].notna())]
    st.caption('📌 Les taux sont calculés uniquement sur les résultats réglés ; les attentes et annulations sont exclues.')
    t1,t2,t3 = st.tabs(['🎟️ Mes combinés','🤖 Prédictions automatiques','📈 Comparaison'])
    with t1:
        a,b,c,d = st.columns(4)
        a.metric('Combinés suivis',int(summary['Combinés suivis'].sum()))
        b.metric('Gagnés',int(summary['Combinés gagnés'].sum()))
        c.metric('Perdus',int(summary['Combinés perdus'].sum()))
        d.metric('À une sélection près',int(summary['À une sélection près'].sum()))
        x,y=st.columns(2)
        x.metric('Réussite des combinés réglés',_pct(100*summary['Combinés gagnés'].sum()/max(1,summary['Combinés gagnés'].sum()+summary['Combinés perdus'].sum())))
        y.metric('Sélections gagnées',int(summary['Sélections gagnées'].sum()))
        st.caption('Chaque sélection est comptée par occurrence dans un combiné. Les paris en attente ou annulés sont exclus des taux.')
        st.dataframe(summary[['Profil','Combinés suivis','Combinés gagnés','Combinés perdus',
                  'Combinés en attente','Réussite combinés (%)','Sélections gagnées',
                  'Sélections perdues','Réussite sélections (%)']],hide_index=True,width='stretch',
                  column_config={'Réussite combinés (%)':st.column_config.ProgressColumn('Réussite combinés',min_value=0,max_value=100,format='%.1f %%'),
                                 'Réussite sélections (%)':st.column_config.ProgressColumn('Réussite sélections',min_value=0,max_value=100,format='%.1f %%')})
        st.subheader('🎯 Combinés manqués à une sélection près')
        st.caption('Uniquement les combinés intégralement réglés : 2/3 = deux sélections gagnées sur trois.')
        st.dataframe(summary[['Profil','À une sélection près','Presque gagnés / perdus (%)',
                    'Détail presque gagnés']],hide_index=True,use_container_width=True)
        st.bar_chart(summary.set_index('Profil')[['À une sélection près']])
        st.subheader('Sélections gagnées et perdues')
        st.bar_chart(summary.set_index('Profil')[['Sélections gagnées','Sélections perdues']])
    with t2:
        a,b,c,d = st.columns(4)
        a.metric('Picks certifiés',len(certified))
        b.metric('Gagnés',int(auto_stats['Gagnés'].sum()))
        c.metric('En attente',int(auto_stats['En attente'].sum()))
        d.metric('Archives non certifiées',len(legacy))
        if len(legacy):
            st.warning(f'{len(legacy)} ancien(s) pick(s) conservé(s) pour audit, mais exclu(s) des performances certifiées.')
        st.caption('Certification = validation_state « roster_verified » ET version renseignée. Une certification ne garantit pas la participation effective du joueur.')
        st.dataframe(auto_stats,hide_index=True,width='stretch',column_config={'Réussite (%)':st.column_config.ProgressColumn('Réussite certifiée',min_value=0,max_value=100,format='%.1f %%')})
        if len(certified):
            st.bar_chart(auto_stats.set_index('Profil')[['Gagnés','Perdus','En attente']])
        else:
            st.info('Aucun pick certifié sur cette période. Les prochains matchs pourront alimenter cette section.')
        with st.expander('🔎 Historique des prédictions automatiques (audit)'):
            if auto.empty:
                st.info('Aucune prédiction automatique enregistrée sur cette période.')
            else:
                profile = st.selectbox('Profil',PROFILES,key='v216_auto_profile')
                subset = auto[auto['profile']==profile].sort_values('kickoff',ascending=False)
                subset=subset.copy()
                subset['probability']=pd.to_numeric(subset['probability'],errors='coerce')*100
                for dt_col in ('kickoff','created_at'):
                    subset[dt_col]=pd.to_datetime(subset[dt_col],utc=True,errors='coerce').dt.tz_convert('Europe/Paris').dt.strftime('%d/%m/%Y · %Hh%M')
                subset=subset.rename(columns={'profile':'Profil','selection':'Sélection','probability':'Estimation (%)','status':'Statut','kickoff':'Match (Paris)','created_at':'Créé (Paris)','validation_state':'Validation','validation_version':'Version','validation_note':'Note'})
                st.dataframe(subset,hide_index=True,width='stretch',column_config={'Estimation (%)':st.column_config.ProgressColumn('Estimation (%)',min_value=0,max_value=100,format='%.1f %%')})
    with t3:
        st.subheader('Comparaison des cinq profils')
        comparison = summary[['Profil','Réussite combinés (%)','Réussite sélections (%)']].merge(
            auto_stats[['Profil','Réussite (%)','Certifiés']],on='Profil',how='left')
        comparison = comparison.rename(columns={'Réussite (%)':'Réussite auto certifiée (%)'})
        st.dataframe(comparison,hide_index=True,width='stretch',column_config={'Réussite sélections (%)':st.column_config.ProgressColumn('Sélections (%)',min_value=0,max_value=100,format='%.1f %%'),'Réussite combinés (%)':st.column_config.ProgressColumn('Combinés (%)',min_value=0,max_value=100,format='%.1f %%'),'Réussite auto certifiée (%)':st.column_config.ProgressColumn('Auto (%)',min_value=0,max_value=100,format='%.1f %%')})
        st.caption('Les taux personnels et automatiques reposent sur des échantillons distincts : ils ne doivent pas être additionnés.')
        st.subheader('📌 Lecture rapide')
        settled = summary.dropna(subset=['Réussite sélections (%)'])
        if len(settled):
            best = settled.sort_values(['Réussite sélections (%)','Sélections gagnées'],ascending=False).iloc[0]
            st.metric('Meilleur taux observé · sélections personnelles',best['Profil'],_pct(best['Réussite sélections (%)']))
        else:
            st.info('Pas encore de sélections personnelles réglées sur la période.')
        st.warning('Rentabilité non calculable : les cotes réellement jouées et les mises ne sont pas enregistrées. Un taux de réussite élevé ne garantit pas un ROI positif.')
