import pandas as pd
from profile_stats_v20 import summarize

def test_profile_counts_and_denominators():
    combos = pd.DataFrame([{'id': 1, 'profile': 'Prudent', 'status': 'won'}, {'id': 2, 'profile': 'Prudent', 'status': 'lost'}, {'id': 3, 'profile': 'Risqué', 'status': 'pending'}])
    legs = pd.DataFrame([{'combo_id': 1, 'status': 'won'}, {'combo_id': 1, 'status': 'won'}, {'combo_id': 2, 'status': 'won'}, {'combo_id': 2, 'status': 'lost'}, {'combo_id': 3, 'status': 'pending'}, {'combo_id': 3, 'status': 'void'}])
    result = summarize(combos, legs).set_index('Profil')
    assert result.loc['Prudent', 'Sélections gagnées'] == 3
    assert result.loc['Prudent', 'Sélections perdues'] == 1
    assert result.loc['Prudent', 'Réussite sélections (%)'] == 75
    assert result.loc['Prudent', 'Réussite combinés (%)'] == 50
    assert result.loc['Risqué', 'Sélections en attente'] == 1
    assert pd.isna(result.loc['Risqué', 'Réussite sélections (%)'])
