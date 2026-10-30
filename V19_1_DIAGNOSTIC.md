# V19.1 — Correctif de lecture ESPN

Le collecteur accepte maintenant les noms d’équipe ESPN dans les liens et blocs HTML, pas seulement les titres h2/h3. Il valide les lignes avant d’écraser les données Supabase.

## Déploiement
1. Copier les fichiers du ZIP à la racine du dépôt GitHub (conserver .github/workflows).
2. Actions → Blessures NHL ESPN V19 → Run workflow.
3. Consulter les logs et Supabase : `SELECT * FROM nhl_injury_sync_v19;`

Si ESPN bloque les requêtes GitHub, le workflow peut encore échouer. Aucun contournement fiable d’ESPN n’a été vérifié ici. Une source officielle alternative sera alors nécessaire.

Une absence de la liste des blessés ne prouve jamais qu’un joueur est confirmé pour jouer.
