"""V22.3 — Récapitulatif des soirées NHL basé exclusivement sur les combinés suivis."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from tracker_v14 import connect, origin_label

PARIS = ZoneInfo('Europe/Paris')
STATUS = {'won':'✅ Gagné', 'lost':'❌ Perdu', 'pending':'⏳ En attente', 'void':'↩️ Annulé'}


def nhl_night(value):
    """Soirée NHL de midi à midi, heure de Paris."""
    local = pd.Timestamp(value)
    if local.tzinfo is None:
        local = local.tz_localize('UTC')
    local = local.tz_convert(PARIS)
    return (local - pd.Timedelta(days=1)).date() if local.hour < 12 else local.date()


def rate(won, lost):
    total = int(won) + int(lost)
    return f'{int(won)/total:.1%}' if total else '—'


def load_data():
    with connect() as conn:
        combos = pd.read_sql_query('''SELECT id, profile, created_at, status FROM tracked_combos ORDER BY created_at DESC''', conn)
        legs = pd.read_sql_query('''SELECT combo_id, match_label, selection, market, probability, kickoff, status
                                    FROM tracked_legs ORDER BY kickoff''', conn)
    return combos, legs


def show():
    st.title('🏆 Récap des soirées NHL')
    st.caption('Uniquement tes combinés enregistrés avec « Suivre ce combiné » · Fuseau Europe/Paris · Une soirée NHL va de midi à midi.')
    try:
        combos, legs = load_data()
    except Exception as exc:
        st.error('Historique des combinés indisponible. Vérifie les tables Supabase et la connexion.')
        st.caption(type(exc).__name__)
        return
    if combos.empty or legs.empty:
        st.info('Aucun combiné suivi enregistré pour le moment.')
        return
    combos['created_at'] = pd.to_datetime(combos['created_at'], utc=True)
    legs['kickoff'] = pd.to_datetime(legs['kickoff'], utc=True, errors='coerce')
    legs = legs.dropna(subset=['kickoff']).copy()
    if legs.empty:
        st.info('Aucun match daté dans les combinés suivis.')
        return
    legs['soirée'] = legs['kickoff'].map(nhl_night)
    combos['Générateur'] = combos['profile'].map(origin_label)
    # Un combiné multi-soirées est attribué une seule fois, à la soirée de son dernier match.
    combo_nights = legs.groupby('combo_id')['soirée'].max()
    combos['soirée'] = combos['id'].map(combo_nights)
    combos = combos.dropna(subset=['soirée']).copy()
    legs = legs[legs['combo_id'].isin(combos['id'])].copy()
    now = datetime.now(PARIS)
    default_night = nhl_night(now)
    available = sorted(set(combos['soirée']) | {default_night}, reverse=True)
    labels = {d: d.strftime('%d/%m/%Y') for d in available}
    chosen = st.selectbox('📅 Soirée NHL', available, format_func=lambda d: labels[d], index=available.index(default_night))
    night_combos = combos[combos['soirée'] == chosen]
    night_legs = legs[legs['combo_id'].isin(night_combos['id'])]
    st.subheader(f'📅 Bilan du {chosen:%d/%m/%Y}')
    cw = int((night_combos.status == 'won').sum()); cl = int((night_combos.status == 'lost').sum())
    lw = int((night_legs.status == 'won').sum()); ll = int((night_legs.status == 'lost').sum())
    a,b,c,d = st.columns(4)
    a.metric('Combinés gagnés', cw)
    b.metric('Combinés perdus', cl)
    c.metric('Réussite combinés', rate(cw,cl))
    d.metric('Combinés en attente / annulés', len(night_combos)-cw-cl)
    a,b,c,d = st.columns(4)
    a.metric('Sélections gagnées', lw)
    b.metric('Sélections perdues', ll)
    c.metric('Réussite sélections', rate(lw,ll))
    d.metric('Sélections en attente / annulées', len(night_legs)-lw-ll)
    st.caption('Les pourcentages excluent les résultats en attente et annulés. Les sélections sont comptées par combiné suivi.')
    st.subheader('📊 Bilan par générateur')
    rows = []
    for origin in ('Combo Builder', 'Sélections gagnantes'):
        subset = night_combos[night_combos['Générateur'] == origin]
        sublegs = night_legs[night_legs['combo_id'].isin(subset['id'])]
        a = int((subset.status=='won').sum()); b = int((subset.status=='lost').sum())
        c = int((sublegs.status=='won').sum()); d = int((sublegs.status=='lost').sum())
        rows.append({'Générateur':origin, 'Combinés suivis':len(subset), 'Combinés gagnés':a,
                     'Combinés perdus':b, 'Réussite combinés':rate(a,b),
                     'Sélections gagnées':c, 'Sélections perdues':d, 'Réussite sélections':rate(c,d)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.subheader('🏆 Mes records personnels')
    night_totals = legs.merge(combos[['id','soirée']],left_on='combo_id',right_on='id',suffixes=('_match',''))
    # Comptabiliser les legs selon la soirée d'attribution du combiné, sans doublonner les combinés.
    win_counts = night_totals.groupby('soirée')['status'].apply(lambda x:int((x=='won').sum()))
    best_night = win_counts.idxmax()
    st.metric('Soirée la plus prolifique', f'{best_night:%d/%m/%Y}', f'{win_counts.loc[best_night]} sélections gagnées', delta_color='off')
    combo_counts = legs.groupby('combo_id')['status'].agg(total='size', won=lambda s:int((s=='won').sum()),lost=lambda s:int((s=='lost').sum()))
    combo_counts['ratio'] = combo_counts.apply(lambda r:r['won']/(r['won']+r['lost']) if r['won']+r['lost'] else 0,axis=1)
    ranked = combo_counts.sort_values(['won','ratio'],ascending=False)
    best_id = ranked.index[0]
    best_combo = combos.set_index('id').loc[best_id]
    st.metric('Combiné le plus prolifique', f"{ranked.loc[best_id,'won']}/{ranked.loc[best_id,'total']} sélections gagnées", f"{best_combo['profile']} · {STATUS.get(best_combo['status'],best_combo['status'])}",delta_color='off')
    winners = combos[combos['Générateur']=='Sélections gagnantes']
    winning_rank = ranked[ranked.index.isin(winners['id'])]
    if not winning_rank.empty:
        w_id = winning_rank.index[0]
        st.metric('Meilleur suivi « Sélections gagnantes »',f"{ranked.loc[w_id,'won']}/{ranked.loc[w_id,'total']} sélections gagnées")
    def detail(combo_id):
        sub = legs[legs.combo_id==combo_id].copy()
        sub['Date du match (Paris)'] = sub['kickoff'].dt.tz_convert(PARIS).dt.strftime('%d/%m/%Y %H:%M')
        sub['Résultat'] = sub['status'].map(lambda s:STATUS.get(s,str(s)))
        sub['Probabilité'] = sub['probability'].map(lambda p:f'{float(p):.1%}' if pd.notna(p) else '—')
        st.dataframe(sub.rename(columns={'match_label':'Match','selection':'Pick','market':'Marché'})[['Date du match (Paris)','Match','Pick','Marché','Résultat','Probabilité']],hide_index=True,use_container_width=True)
    with st.expander('🏆 Voir les picks de ma meilleure soirée'):
        for row in combos[combos['soirée']==best_night].itertuples():
            st.markdown(f'**{row.Générateur} · {row.profile} · {STATUS.get(row.status,row.status)}**')
            detail(row.id)
    with st.expander('🎯 Voir les picks de mon combiné le plus prolifique'):
        detail(best_id)
    if not winning_rank.empty:
        with st.expander('⭐ Voir mes meilleurs picks « Sélections gagnantes »'):
            detail(w_id)
    st.subheader('📋 Derniers combinés suivis')
    for row in night_combos.sort_values('created_at',ascending=False).itertuples():
        count = len(night_legs[night_legs.combo_id==row.id])
        with st.expander(f'{row.Générateur} · {row.profile} · {count} picks · {STATUS.get(row.status,row.status)}'):
            st.caption(f"Enregistré le {row.created_at.tz_convert(PARIS):%d/%m/%Y à %H:%M} (Paris)")
            detail(row.id)
    st.caption('Un combiné comportant plusieurs soirées est rattaché à la soirée de son dernier match, une seule fois dans les totaux.')
