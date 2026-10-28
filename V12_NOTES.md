# ErlHockey V12 — Betting Center

## Installation
Remplacer les fichiers du dépôt GitHub par ceux de ce ZIP, en conservant les secrets Streamlit existants (`SUPABASE_DB_URL`). Aucune migration SQL nécessaire pour ce module. Aucun changement des workflows de collecte ni des anciennes pages.

## Nouveautés
- Navigation « 🎯 Betting Center V12 » : analyses joueurs (1+ but, 1+ point, 2+ points), fenêtres 5/10/20 matchs, historique détaillé.
- Analyse des équipes : buts attendus et probabilités exploratoires de totaux 4,5 / 5,5 / 6,5, sans prédiction du vainqueur tant que le modèle n’est pas validé.
- Signalement des historiques incomplets.

## Limites importantes
- Estimations expérimentales non calibrées et non backtestées ; ne pas les considérer comme des recommandations de mise.
- Les scores stockés peuvent inclure prolongations et tirs au but. Les estimations de totaux sont donc approximatives. Le marché vainqueur n’est pas encore modélisé dans cette V12.
- Les tirs cadrés ne sont pas collectés.
- Aucun bookmaker, cote ou valeur attendue calculée.
- Aucun test d'intégration en direct contre Supabase n'a été réalisé.
