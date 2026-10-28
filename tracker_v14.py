"""V14: snapshot and settle user-followed combos. Requires sql/v14_tracker.sql."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import psycopg
import streamlit as st

PARIS=ZoneInfo('Europe/Paris')

def connect():
    return psycopg.connect(st.secrets['SUPABASE_DB_URL'], connect_timeout=15)

def follow(profile, combo):
    """Snapshot selections before kickoff; never overwrite a prediction."""
    now=datetime.now(timezone.utc)
    if any(p['time'].astimezone(timezone.utc) <= now for p in combo):
        raise ValueError('Un match a déjà commencé : suivi impossible.')
    payload=[{'game_id':int(p['game_id']), 'match':str(p['match']),
              'selection':str(p['selection']), 'market':str(p['market']),
              'probability':float(p['probability']), 'kickoff':p['time'].isoformat()}
             for p in combo]
    if len({p['game_id'] for p in payload})!=len(payload):
        raise ValueError('Un seul choix par match est autorisé.')
    signature=hashlib.sha256(json.dumps([profile,payload],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO tracked_combos (profile, signature, theoretical_probability)
                VALUES (%s,%s,%s) ON CONFLICT (signature) DO NOTHING RETURNING id''',
                (profile,signature,__import__('math').prod(p['probability'] for p in payload)))
            row=cur.fetchone()
            if row is None:
                return False
            combo_id=row[0]
            for p in payload:
                cur.execute('''INSERT INTO tracked_legs (combo_id, game_id, match_label, selection, market, probability, kickoff)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)''', (combo_id,p['game_id'],p['match'],p['selection'],p['market'],p['probability'],p['kickoff']))
    return True

def show():
    st.caption('Historique des combinés cochés avant les matchs. Un combiné est gagné seulement si toutes ses sélections gagnent.')
    period=st.radio('Période', ['7 jours','30 jours','365 jours','Tout'], horizontal=True)
    days={'7 jours':7,'30 jours':30,'365 jours':365,'Tout':None}[period]
    try:
        with connect() as conn:
            df=pd.read_sql_query('''SELECT c.id,c.profile,c.created_at,c.status,c.theoretical_probability,
                COUNT(l.id) AS selections, COUNT(*) FILTER (WHERE l.status='won') AS legs_won,
                COUNT(*) FILTER (WHERE l.status='lost') AS legs_lost
                FROM tracked_combos c JOIN tracked_legs l ON l.combo_id=c.id
                GROUP BY c.id ORDER BY c.created_at DESC''',conn)
            legs=pd.read_sql_query('''SELECT l.combo_id,l.match_label,l.selection,l.status,l.probability,l.kickoff
                FROM tracked_legs l ORDER BY l.kickoff''',conn)
    except Exception as exc:
        st.error('Suivi indisponible. Exécute d’abord sql/v14_tracker.sql dans Supabase et vérifie SUPABASE_DB_URL.')
        st.caption(f'Détail technique : {type(exc).__name__}')
        return
    if df.empty:
        st.info('Aucun combiné suivi pour le moment. Coche « Suivre ce combiné » dans le Combo Builder avant le début des matchs.')
        return
    df['created_at']=pd.to_datetime(df.created_at,utc=True)
    if days:
        df=df[df.created_at>=pd.Timestamp.now(tz='UTC')-pd.Timedelta(days=days)]
    if df.empty:
        st.info('Aucun combiné sur cette période.')
        return
    st.subheader('Fiabilité de mes combinés suivis')
    summary=[]
    for profile, group in df.groupby('profile'):
        settled=group[group.status.isin(['won','lost'])]
        wins=int((settled.status=='won').sum())
        summary.append({'Profil':profile,'Suivis':len(group),'Terminés':len(settled),
                        'Gagnés':wins,'Perdus':int((settled.status=='lost').sum()),
                        'Réussite':f'{wins/len(settled):.1%}' if len(settled) else '—',
                        'En attente / annulés':len(group)-len(settled)})
    st.dataframe(pd.DataFrame(summary),hide_index=True,use_container_width=True)
    settled=df[df.status.isin(['won','lost'])]
    if len(settled):
        st.metric('Taux de réussite global',f'{(settled.status=="won").mean():.1%}',help='Combinés gagnés / combinés terminés (hors attente et annulation).')
    else:
        st.info('Pas encore de combinés terminés : aucun taux de réussite calculable.')
    st.subheader('Détail des suivis')
    for row in df.itertuples():
        with st.expander(f'{row.profile} · {row.selections} sélections · {row.status} · {row.created_at.tz_convert(PARIS):%d/%m/%Y %H:%M}'):
            sub=legs[legs.combo_id==row.id]
            st.dataframe(sub[['match_label','selection','status','probability','kickoff']],hide_index=True,use_container_width=True)
    st.caption('Ce suivi mesure les résultats des combinés sélectionnés, pas la rentabilité. Aucun pari n’est placé depuis ErlHockey.')
