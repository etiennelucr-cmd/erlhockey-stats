# ErlHockey V14 — Installation

1. Sauvegarder le dépôt GitHub actuel et créer une branche `test-v14`.
2. Déployer tous les fichiers en préservant `.github/workflows/`.
3. Exécuter **une fois** `sql/v14_tracker.sql` dans le SQL Editor de Supabase. Les tables sont privées et accessibles au backend avec `SUPABASE_DB_URL`.
4. Vérifier que `SUPABASE_DB_URL` existe dans les secrets Streamlit ET GitHub Actions. Ne jamais publier l’URL de connexion.
5. Lancer l’application : dans **Combo Builder V14**, ouvrir un profil, choisir un combo, cliquer **Suivre ce combiné** avant le début du premier match.
6. Le workflow de collecte lance ensuite `settle_v14.py` pour régler les sélections sur les matchs terminés. Consulter **Mes combinés V14**.

## Limites
- Aucune prédiction passée n’est reconstituée ; l’historique commence à la première sauvegarde.
- Les marchés 60 minutes (domicile/nul/extérieur) sont marqués `void` faute de score à 60 minutes stocké ; les tirs ne sont pas encore disponibles.
- Une sélection joueur non identifiable dans le boxscore est annulée plutôt que déclarée perdante.
- Si une sélection est perdue, le combiné est perdu. Si toutes gagnent, il est gagné. Sinon, un combiné entièrement terminé avec une sélection annulée est `void`.
- Ce suivi est partagé par tous les utilisateurs de l’application : aucune authentification individuelle n’est en place. Ne pas exposer ce module publiquement comme un espace privé sans ajouter une authentification.
- Les probabilités sont expérimentales et non calibrées ; les résultats suivis ne prouvent aucune rentabilité.
