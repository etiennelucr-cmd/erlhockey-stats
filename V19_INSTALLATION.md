# ErlHockey V19 — synchronisation ESPN des blessures

1. Déployer tous les fichiers, y compris `espn_injuries_v19.py`, `requirements.txt` et `.github/workflows/blessures-espn-v19.yml`.
2. Vérifier que le secret GitHub `SUPABASE_DB_URL` est présent. La synchronisation crée automatiquement les tables `nhl_injury_reports_v19` et `nhl_injury_sync_v19` avec le compte de base utilisé par GitHub Actions (qui doit avoir les droits CREATE TABLE).
3. Déclencher manuellement **Actions → Blessures NHL ESPN V19 → Run workflow**. Puis consulter les logs. Une synchronisation est planifiée toutes les 3 heures.
4. La page ESPN peut bloquer les robots ou modifier son HTML. Dans ce cas, le workflow échoue, la dernière capture est conservée mais périme après 24 heures. Aucun joueur inconnu ne sera éligible sans confirmation manuelle si ESPN n'est pas frais.
5. ESPN fournit des blessures signalées, pas une liste officielle des joueurs confirmés. Les joueurs non listés sont étiquetés « non confirmés ». En Combo Builder, cocher le mode strict pour n'accepter que les joueurs confirmés manuellement dans `player_availability_v17.csv`.
6. Les noms et abréviations d'équipe doivent correspondre entre ESPN et la base. Vérifier les exclusions sur un match test avant utilisation. Ne pas assimiler un joueur absent d'ESPN à un joueur certain de participer.

## Limitations

Le parsing ESPN est dépendant de la structure HTML et peut échouer. Il n'existe pas ici de contrat d'API officiel ESPN ni de garantie d'accès automatisé. Les données ESPN peuvent être incomplètes ou en retard ; contrôler les alignements officiels à l'approche du match. Les marchés matchs et le règlement Supabase V18 ne sont pas modifiés.
