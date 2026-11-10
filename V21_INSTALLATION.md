# ErlHockey V21 — prédictions automatiques

## Activation (obligatoire)
1. Exécuter `v21_auto_picks.sql` une fois dans l'éditeur SQL Supabase.
2. Vérifier le secret GitHub Actions `SUPABASE_DB_URL`.
3. Déployer tous les fichiers, y compris `.github/workflows/v21-auto-picks.yml`.
4. Dans GitHub Actions, lancer une fois **V21 Predictions automatiques** via `workflow_dispatch` et contrôler les logs.
5. Ouvrir **NHL Picks** pour comparer les statistiques **Automatique** et **Mes choix**.

Le workflow s'exécute toutes les 30 minutes (UTC), collecte les rencontres NHL aujourd'hui/demain en heure de Paris, calcule les sélections à partir de matchs terminés avant la génération, et fige **au maximum un pick par match et profil**. Les exécutions répétées n'écrasent jamais un pick enregistré. Il vérifie aussi les picks en attente à partir des statistiques collectées par `collect_nhl.py`.

### Limites
- Les picks automatiques commencent **après l'installation** : aucun historique n'est inventé.
- Un match absent des données NHL ou sans joueurs avec cinq matchs exploitables n'a pas de suggestion.
- L'absence de données joueur après le match produit `void`, pas une perte automatique.
- Le résultat est calculé sur la base des données NHL collectées; la collecte doit tourner avant le règlement.
- Le générateur V20 n'est pas calibré et utilise les dix derniers matchs : la V21 améliore la mesure, **pas** la précision prédictive.
- Les picks automatiques sont des sélections individuelles, **pas** des combinés multi-matchs. Les statistiques « 5/6 » restent liées aux combinés suivis dans le module existant.
- Aucun calcul de rentabilité n'est possible sans cotes et mises.
- La génération horaire peut manquer un match si le workflow échoue avant le coup d'envoi; consulter les logs GitHub Actions.
