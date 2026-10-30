"""V14: snapshot and settle user-followed combos. Requires sql/v14_tracker.sql."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import psycopg
import streamlit as st

PARIS=ZoneInfo('Europe/Paris')

def origin_label(profile):
    return 'Sélections gagnantes' if str(profile).startswith('Sélections gagnantes') else 'Combo Builder'


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
    df['origine']=df['profile'].map(origin_label)
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
    st.subheader('Bilan par générateur')
    origin_rows=[]
    for origin, group in df.groupby('origine'):
        completed=group[group.status.isin(['won','lost'])]
        origin_legs=legs[legs.combo_id.isin(group.id)]
        nw=int((origin_legs.status=='won').sum())
        nl=int((origin_legs.status=='lost').sum())
        cw=int((completed.status=='won').sum())
        cl=int((completed.status=='lost').sum())
        origin_rows.append({'Origine':origin,'Combinés suivis':len(group),
                            'Combinés gagnés':cw,'Combinés perdus':cl,
                            'Ratio combinés':f'{cw/(cw+cl):.1%}' if cw+cl else '—',
                            'Sélections gagnées':nw,'Sélections perdues':nl,
                            'Ratio sélections':f'{nw/(nw+nl):.1%}' if nw+nl else '—'})
    st.dataframe(pd.DataFrame(origin_rows),hide_index=True,use_container_width=True)
    st.caption('Chaque sélection suivie est comptée une fois par combiné enregistré. '
               'Une même prédiction suivie dans deux combinés différents compte dans chacun de leurs bilans.')
    st.subheader('Détail des suivis')
    for row in df.itertuples():
        with st.expander(f'{row.origine} · {row.profile} · {row.selections} sélections · {row.status} · {row.created_at.tz_convert(PARIS):%d/%m/%Y %H:%M}'):
            sub=legs[legs.combo_id==row.id]
            st.dataframe(sub[['match_label','selection','status','probability','kickoff']],hide_index=True,use_container_width=True)
    st.caption('Ce suivi mesure les résultats des combinés sélectionnés, pas la rentabilité. Aucun pari n’est placé depuis ErlHockey.')

def dashboard_summary():
    """Real tracked combo and leg statuses, no fabricated results."""
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status, count(*) FROM tracked_combos GROUP BY status")
                combos=dict(cur.fetchall())
                cur.execute("SELECT status, count(*) FROM tracked_legs GROUP BY status")
                legs=dict(cur.fetchall())
                cur.execute('''SELECT c.profile,c.created_at,c.status,
                    COUNT(l.id) AS total,
                    COUNT(*) FILTER (WHERE l.status='won') AS won,
                    COUNT(*) FILTER (WHERE l.status='lost') AS lost,
                    COUNT(*) FILTER (WHERE l.status NOT IN ('won','lost')) AS unresolved
                    FROM tracked_combos c JOIN tracked_legs l ON l.combo_id=c.id
                    GROUP BY c.id ORDER BY c.created_at DESC LIMIT 8''')
                recent=cur.fetchall()
    except Exception as exc:
        st.info('Bilan indisponible : vérifie la connexion Supabase et les tables V14.')
        st.caption(type(exc).__name__)
        return
    won=int(combos.get('won',0)); lost=int(combos.get('lost',0))
    a,b,c,d,e=st.columns(5)
    a.metric('Combinés gagnés',won)
    b.metric('Combinés perdus',lost)
    c.metric('Sélections gagnées',int(legs.get('won',0)))
    d.metric('Sélections perdues',int(legs.get('lost',0)))
    leg_won=int(legs.get('won',0)); leg_lost=int(legs.get('lost',0))
    e.metric('Ratio sélections',f'{leg_won/(leg_won+leg_lost):.1%}' if leg_won+leg_lost else '—',help='Gagnées / (gagnées + perdues), hors pending et void.')
    st.caption(f'Réussite combinés : {won/(won+lost):.1%}' if won+lost else 'Réussite combinés : — (aucun combiné terminé)')
    try:
        with connect() as conn:
            origins=pd.read_sql_query("""SELECT CASE WHEN c.profile LIKE 'Sélections gagnantes%' THEN 'Sélections gagnantes' ELSE 'Combo Builder' END AS origine,
                COUNT(DISTINCT c.id) AS combos_suivis,
                COUNT(DISTINCT c.id) FILTER (WHERE c.status='won') AS combos_gagnes,
                COUNT(DISTINCT c.id) FILTER (WHERE c.status='lost') AS combos_perdus,
                COUNT(l.id) FILTER (WHERE l.status='won') AS selections_gagnees,
                COUNT(l.id) FILTER (WHERE l.status='lost') AS selections_perdues
                FROM tracked_combos c LEFT JOIN tracked_legs l ON l.combo_id=c.id GROUP BY 1 ORDER BY 1""",conn)
        if not origins.empty:
            origins['Ratio sélections']=origins.apply(lambda r: f"{r.selections_gagnees/(r.selections_gagnees+r.selections_perdues):.1%}" if r.selections_gagnees+r.selections_perdues else '—',axis=1)
            st.markdown('**Bilan par générateur**')
            st.dataframe(origins.rename(columns={'origine':'Origine','combos_suivis':'Combinés suivis','combos_gagnes':'Combinés gagnés','combos_perdus':'Combinés perdus','selections_gagnees':'Sélections gagnées','selections_perdues':'Sélections perdues'}),hide_index=True,use_container_width=True)
    except Exception:
        st.caption('Détail par générateur temporairement indisponible.')
    if recent:
        st.markdown('**Derniers combinés suivis**')
        rows=[]
        for profile,created,status,total,leg_won,leg_lost,unresolved in recent:
            rows.append({'Origine':origin_label(profile),'Profil':profile,'Date (Paris)':created.astimezone(PARIS).strftime('%d/%m %H:%M'),
                         'Résultat':{'won':'✅ Gagné','lost':'❌ Perdu','pending':'⏳ En attente','void':'↩️ Annulé'}.get(status,status),
                         'Sélections gagnées':f'{leg_won}/{total}', 'Sélections perdues':int(leg_lost),
                         'En attente / annulées':int(unresolved)})
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    else:
        st.info('Aucun combiné suivi pour le moment.')
