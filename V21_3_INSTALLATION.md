# ErlHockey V21.3 — Installation

## 1. Supabase (obligatoire, AVANT GitHub)
Ouvrir SQL Editor, coller le contenu de `V21_3_MIGRATION.sql`, cliquer Run.
Cela ajoute trois colonnes de traçabilité, sans supprimer ni modifier les 35 anciennes prédictions. Les anciennes lignes prennent automatiquement l'état `legacy_unverified`.

## 2. GitHub
Décompresser ce ZIP. Dans le dépôt, remplacer au minimum :
- `auto_picks_v21.py`
- `auto_dashboard_v21.py`
- ajouter `V21_3_MIGRATION.sql` et ce guide si souhaité.
Commit changes, puis Actions > V21 Predictions automatiques > Run workflow.

## 3. Logs attendus
Le workflow affichera le nombre de matchs futurs, les effectifs NHL consultés, les candidats écartés, les doublons ignorés et les picks évalués. Sur les mêmes matchs, 0 nouveau pick reste normal.

## 4. SQL de contrôle
SELECT validation_state, validation_version, status, COUNT(*)
FROM v21_auto_picks
GROUP BY validation_state, validation_version, status
ORDER BY validation_state, validation_version, status;

## Limites importantes
- La présence dans un effectif NHL ne confirme pas une participation au match.
- Un pick existant n'est jamais remplacé silencieusement.
- Les anciens picks sont conservés pour audit et exclus du taux automatique certifié ; ils ne sont pas rétroactivement certifiés.
- Une absence de statistiques peut aussi signifier qu'un joueur n'a pas joué ; sans preuve fiable de participation/absence, le règlement reste en attente.
- Les avertissements pandas/psycopg ne sont pas bloquants.
- Les contrôles en ligne NHL/Supabase nécessitent un essai réel sur GitHub ; non réalisés dans cet environnement.
