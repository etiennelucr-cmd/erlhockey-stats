"""Display-only formatting for NHL pick tables; no changes to persisted data."""
import pandas as pd

STATUSES = {'pending':'En attente','won':'Gagné','lost':'Perdu','void':'Annulé'}

def paris_date(values):
    return pd.to_datetime(values, utc=True, errors='coerce').dt.tz_convert('Europe/Paris').dt.strftime('%d/%m/%Y · %Hh%M').fillna('—')

def probability(values):
    return pd.to_numeric(values, errors='coerce').mul(100).round(1)

def audit_view(frame, technical=False):
    """Readable audit view, optionally including certification diagnostics."""
    if frame.empty:
        return pd.DataFrame()
    f=frame.copy()
    f['probability']=probability(f['probability'])
    for col in ('kickoff','created_at'):
        f[col]=paris_date(f[col])
    f['status']=f['status'].map(STATUSES).fillna(f['status'])
    f=f.rename(columns={'profile':'Profil','selection':'Sélection','probability':'Estimation (%)',
       'status':'Statut','kickoff':'Match (Paris)','created_at':'Créé (Paris)',
       'validation_state':'Validation','validation_version':'Version','validation_note':'Note'})
    columns=['Sélection','Estimation (%)','Match (Paris)','Statut','Créé (Paris)']
    if technical:
        columns += ['Validation','Version','Note']
        for col in ('Validation','Version','Note'):
            if col in f:
                f[col]=f[col].fillna('—').replace('', '—')
    return f[[c for c in columns if c in f.columns]]
