# ErlHockey V21.4 — NHL officiel et traçabilité

## Changements
- Effectif NHL courant = source de vérité pour l'équipe du joueur, même si ses statistiques historiques indiquent une autre équipe après un transfert.
- Vérification finale de chaque sélection avant écriture Supabase.
- Diagnostics sur les matchs, effectifs, joueurs historiques, candidats, exclusions, transferts, propositions et doublons.
- Les anciens picks ne sont ni supprimés ni remplacés.
- Covers est une référence de contrôle **manuel**, non une API automatisée : aucun scraping fragile ou validation fictive.
- Les blessures, alignements et participations ne sont pas certifiés par ce contrôle d'effectif.

## Installation
1. La migration SQL `V21_3_MIGRATION.sql` doit déjà avoir été appliquée. Si ce n'est pas le cas, l'exécuter d'abord dans Supabase SQL Editor.
2. Dans GitHub, remplacer `auto_picks_v21.py` par celui du ZIP. Les autres fichiers peuvent être conservés ; aucun changement de workflow n'est requis.
3. Commit changes → Actions → V21 Predictions automatiques → Run workflow.
4. Ouvrir les logs de `Generer et verifier les picks V21`.
5. Si 0 ajout et doublons > 0 : les anciens picks sont protégés par `UNIQUE(profile,game_id)` ; ne pas les supprimer pour forcer une réécriture.

## Vérification SQL
```sql
SELECT validation_state, validation_version, status, COUNT(*)
FROM public.v21_auto_picks
GROUP BY 1,2,3 ORDER BY 1,2,3;
```

## Tests
`python -m unittest test_v213_logic.py test_v214_validation.py`

## Limites
Le contrôle d'effectif officiel ne prouve pas la participation effective. Les joueurs sans historique suffisant ne sont pas proposés. L'API NHL et la connexion Supabase doivent être validées en exécution réelle. La probabilité reste une estimation statistique exploratoire.
