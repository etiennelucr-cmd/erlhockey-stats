"""Shared auto-pick accounting. Historical predictions count without retroactive certification."""
import pandas as pd

CERTIFIED_STATES = frozenset({'roster_verified', 'roster_injury_checked'})

def certified_mask(frame):
    if frame.empty:
        return pd.Series(False, index=frame.index, dtype=bool)
    return (frame['validation_state'].isin(CERTIFIED_STATES)
            & frame['validation_version'].notna()
            & frame['validation_version'].astype(str).str.strip().ne(''))

def summary(frame, profiles, label='Automatique (tous)'):
    rows=[]
    for profile in profiles:
        part=frame[frame['profile'].eq(profile)]
        won=int(part['status'].eq('won').sum())
        lost=int(part['status'].eq('lost').sum())
        rows.append({'Profil':profile,'Origine':label,'Total':len(part),'Gagnés':won,'Perdus':lost,
                     'En attente':int(part['status'].eq('pending').sum()),
                     'Annulés':int(part['status'].eq('void').sum()),
                     'Réussite':f'{won/(won+lost):.1%}' if won+lost else '—',
                     'Réussite (%)':round(100*won/(won+lost),2) if won+lost else None})
    return pd.DataFrame(rows)
