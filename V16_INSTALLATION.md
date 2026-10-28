# ErlHockey V16 — NHL Picks automatique

- NHL Picks affiche automatiquement les 10 joueurs les mieux classés parmi les matchs à venir aujourd’hui et demain (heure de Paris).
- Cartes joueurs : points et buts sur les 5 derniers matchs, séries positives/négatives, fréquences sur 5/10/20 matchs si disponibles.
- Le classement reste heuristique, sans calibration probabiliste ; il ne prédit pas les gains.
- Les six pages et le suivi des combinés Supabase sont conservés.
- Aucune migration SQL. Déployer le contenu de `erlhockey-stats-main/` sur une branche de test GitHub.
- Contrôler le rendu Streamlit et les données réelles après déploiement.
