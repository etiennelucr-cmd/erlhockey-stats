"""V20 combo ranking: maximize estimated joint probability within each profile.

Probabilities remain uncalibrated; independence is an explicit approximation.
"""
import math
from itertools import combinations
PROFILES = {
    "Prudent": {"range": (0.72, 1.0)},
    "Modéré": {"range": (0.62, 0.82)},
    "Équilibré": {"range": (0.50, 0.72)},
    "Risqué": {"range": (0.35, 0.60)},
    "Ultra risqué": {"range": (0.15, 0.45)},
}


def build_combos(picks, legs=4, top_n=3, profile='Équilibré', diversify=False):
    if not isinstance(legs, int) or legs < 2:
        raise ValueError('Le nombre de sélections doit être au moins 2')
    if not isinstance(top_n, int) or top_n < 1:
        raise ValueError('top_n doit être positif')
    if profile not in PROFILES:
        raise ValueError('Profil inconnu')
    low, high = PROFILES[profile]['range']
    by_game = {}
    for pick in picks:
        p = pick.get('probability')
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not low <= p <= high or p <= 0:
            continue
        if 'game_id' not in pick or 'selection' not in pick:
            continue
        by_game.setdefault(pick['game_id'], []).append(pick)
    if len(by_game) < legs:
        return []
    # For maximum probability, the best selection per match is sufficient.
    # Diversity is only a secondary tie-break among equally likely combinations.
    best = []
    for gid, rows in by_game.items():
        best.append(max(rows, key=lambda x: (x['probability'], str(x['selection']))))
    # No arbitrary truncation of fixture pool. Only the top (legs + top_n - 1)
    # fixtures can contribute to top_n combinations under independent products.
    best.sort(key=lambda x: (-x['probability'], str(x['game_id'])))
    best = best[:min(len(best), legs + top_n - 1)]
    candidates = []
    for combo in combinations(best, legs):
        logp = sum(math.log(p['probability']) for p in combo)
        diversity = len({p.get('market') for p in combo}) if diversify else 0
        ordered = tuple(sorted(combo, key=lambda x: (str(x.get('time', '')), str(x['game_id']))))
        candidates.append((logp, diversity, ordered))
    candidates.sort(key=lambda x: (-x[0], -x[1], tuple(str(p['game_id']) for p in x[2])))
    return [(math.exp(logp), combo) for logp, _, combo in candidates[:top_n]]


def show(db_query):
    # Existing UI stays functional while the builder is upgraded by rebinding
    # its module-global function used by the Streamlit show() implementation.
    import combo_v12
    original = combo_v12.build_combos
    combo_v12.build_combos = build_combos
    try:
        return combo_v12.show(db_query)
    finally:
        combo_v12.build_combos = original
