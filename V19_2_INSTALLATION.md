# V19.2 — Collecteur ESPN JSON avec secours HTML

1. Copier les fichiers dans GitHub sur la branche main.
2. Dans Actions, lancer « Blessures NHL ESPN V19 ».
3. Dans Supabase, vérifier `SELECT * FROM nhl_injury_sync_v19;` et `SELECT COUNT(*) FROM nhl_injury_reports_v19;`.
4. Une exécution verte ne confirme pas les alignements : ESPN fournit des blessures, pas les compositions officielles.

Le collecteur teste d’abord l’API JSON non officielle ESPN (`site.api.espn.com/.../injuries`), puis le HTML en secours. Si les deux échouent, l’exécution reste rouge, la dernière photo de blessures est préservée et l’erreur est inscrite dans `nhl_injury_sync_v19`.

**Limites** : l’API ESPN n’est pas contractuelle et son format n’a pas été validé en direct dans cet environnement. Une liste vide n’est jamais considérée comme une confirmation que tous les joueurs sont disponibles. Aucun nouveau SQL requis. Ne pas supprimer le fichier CSV de confirmation manuelle.
