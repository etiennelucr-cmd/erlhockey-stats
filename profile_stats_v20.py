"""Cumulative, settled results by Combo Builder risk profile."""
import pandas as pd

PROFILES = ['Prudent', 'Modéré', 'Équilibré', 'Risqué', 'Ultra risqué']


def summarize(combos, legs):
    """One leg per tracked occurrence; pending/void excluded from win rates."""
    rows = []
    for profile in PROFILES:
        c = combos[combos['profile'] == profile]
        l = legs[legs['combo_id'].isin(c['id'])]
        cw = int((c['status'] == 'won').sum())
        cl = int((c['status'] == 'lost').sum())
        lw = int((l['status'] == 'won').sum())
        ll = int((l['status'] == 'lost').sum())
        # A near miss is a fully resolved combo with exactly one lost leg.
        # Exclude pending/void legs to avoid counting unfinished or refunded bets.
        profile_legs = l.groupby('combo_id')['status'].agg(list).to_dict()
        near_misses = []
        for combo_id, statuses in profile_legs.items():
            if statuses and all(status in ('won', 'lost') for status in statuses):
                if statuses.count('lost') == 1 and statuses.count('won') == len(statuses) - 1:
                    near_misses.append((combo_id, len(statuses)))
        # Denominator: all completely resolved lost combos with valid legs.
        resolved_losses = sum(
            1 for statuses in profile_legs.values()
            if statuses and all(status in ('won', 'lost') for status in statuses)
            and 'lost' in statuses
        )
        near_count = len(near_misses)
        near_pct = round(100 * near_count / resolved_losses, 2) if resolved_losses else None
        breakdown = {}
        for _, size in near_misses:
            label = f'{size-1}/{size}'
            breakdown[label] = breakdown.get(label, 0) + 1
        rows.append({'Profil': profile, 'Combinés suivis': len(c),
                     'Combinés gagnés': cw, 'Combinés perdus': cl,
                     'À une sélection près': near_count,
                     'Presque gagnés / perdus (%)': near_pct,
                     'Détail presque gagnés': ', '.join(f'{k} : {v}' for k, v in sorted(breakdown.items())) or '—',
                     'Réussite combinés (%)': round(100*cw/(cw+cl), 2) if cw+cl else None,
                     'Sélections gagnées': lw, 'Sélections perdues': ll,
                     'Réussite sélections (%)': round(100*lw/(lw+ll), 2) if lw+ll else None,
                     'Sélections en attente': int((l['status'] == 'pending').sum()),
                     'Sélections annulées': int((l['status'] == 'void').sum())})
    return pd.DataFrame(rows)


def show():
    import streamlit as st
    from tracker_v14 import connect
    st.subheader('📊 Bilan cumulé par profil de risque')
    st.caption('Historique de tous les combinés enregistrés dans « Suivre ce combiné ». Chaque sélection est comptée par occurrence dans un combiné, y compris lorsqu’elle figure dans plusieurs combinés.')
    try:
        with connect() as conn:
            combos = pd.read_sql_query('SELECT id, profile, status, created_at FROM tracked_combos', conn)
            legs = pd.read_sql_query('SELECT combo_id, status FROM tracked_legs', conn)
    except Exception as exc:
        st.error('Impossible de charger les suivis Supabase. Vérifie SUPABASE_DB_URL et les tables tracked_combos / tracked_legs.')
        st.caption(type(exc).__name__)
        return
    if combos.empty:
        st.info('Aucun combiné enregistré. Utilise « Suivre ce combiné » pour alimenter ces statistiques.')
        return
    combos['created_at'] = pd.to_datetime(combos['created_at'], utc=True)
    period = st.selectbox('Période des combinés créés', ['Tout l’historique', '7 jours', '30 jours', '90 jours', '365 jours'])
    durations = {'7 jours': 7, '30 jours': 30, '90 jours': 90, '365 jours': 365}
    if period in durations:
        combos = combos[combos['created_at'] >= pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=durations[period])]
    summary = summarize(combos, legs)
    st.dataframe(summary, hide_index=True, use_container_width=True)
    st.subheader('🎯 Combinés manqués à une sélection près')
    st.caption('Exemples : 5/6 = cinq sélections gagnées sur six, 2/3 = deux sur trois. Seuls les combinés dont toutes les sélections sont gagnées ou perdues sont comptés. Les annulations et les attentes sont exclues.')
    near = summary[['Profil', 'À une sélection près', 'Presque gagnés / perdus (%)', 'Détail presque gagnés']].copy()
    near = near.rename(columns={'Presque gagnés / perdus (%)': '% des combinés perdus entièrement vérifiés'})
    st.dataframe(near, hide_index=True, use_container_width=True)
    st.bar_chart(summary.set_index('Profil')[['À une sélection près']])
    settled = summary.dropna(subset=['Réussite sélections (%)'])
    if not settled.empty:
        best = settled.sort_values(['Réussite sélections (%)', 'Sélections gagnées'], ascending=False).iloc[0]
        st.metric('Meilleur taux de réussite des sélections (observé)', best['Profil'], f"{best['Réussite sélections (%)']:.2f} %")
        st.caption('Classement descriptif, sensible à la taille des échantillons. Un taux de réussite élevé ne prouve pas la rentabilité.')
    else:
        st.info('Aucune sélection gagnée ou perdue pour la période choisie.')
    st.subheader('Comparaison des profils')
    st.bar_chart(summary.set_index('Profil')[['Sélections gagnées', 'Sélections perdues']])
    st.subheader('Rentabilité : données manquantes')
    st.warning('Le suivi actuel ne stocke ni les cotes réelles ni les mises. Impossible de calculer honnêtement le bénéfice, le ROI ou le profil le plus rentable. Le meilleur taux de réussite n’est pas nécessairement le plus rentable.')
    st.caption('Pour calculer le ROI, il faudra enregistrer la cote effectivement jouée et la mise de chaque combiné, puis calculer (gains nets − pertes) / total des mises. Les combinés annulés nécessitent une règle de remboursement explicite.')
