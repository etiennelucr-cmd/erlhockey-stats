# ErlHockey V18 — Sélections gagnantes

Nouvelle page **🏆 Sélections gagnantes** : récupère les sélections joueurs historiquement **gagnées** dans `tracked_legs` (statuts `won`/`lost` uniquement), puis vérifie si le joueur rejoue **ce soir**, **demain** ou sur les deux soirées (heure de Paris, midi à midi).

- Association **exacte** du nom du joueur, du marché (points/buts) et de la sélection : aucune substitution de marché.
- Filtres : minimum de victoires historiques, ratio gagnées / (gagnées + perdues), nombre de jambes.
- Un seul choix par match ; impossible de suivre après le coup d'envoi.
- Les joueurs non confirmés sont exclus selon `player_availability_v17.csv` (maximum 24 h). Sans statuts récents, la page peut rester vide. Pas de flux de blessures automatique.
- Enregistrer via **Suivre ce combiné historique** dans les tables V14 existantes. Aucun nouveau SQL.
- Tableau de bord : sélections gagnées, perdues et ratio hors `pending`/`void`.

## Déploiement

Décompresser puis remplacer les fichiers du dépôt GitHub. Conserver les secrets `SUPABASE_DB_URL` et les workflows existants. Déployer d'abord sur une branche de test. Après les premiers matchs réglés, vérifier les résultats dans **Mes combinés**.

**Limites :** seules les sélections joueurs (1+ point, 2+ points, 1+ but) sont réutilisées automatiquement. Les marchés « domicile/extérieur » ne sont pas réutilisés sans vérification de l'identité des équipes. Les résultats passés ne prédisent pas les suivants ; aucune cote ni rentabilité n'est garantie.


## Correctif suivi unifié
Les combinés de la page « Sélections gagnantes » utilisent le même bouton de suivi et les mêmes tables `tracked_combos` et `tracked_legs` que le Combo Builder. Ils apparaissent dans « Mes combinés » et le tableau de bord, avec une ventilation par origine. Les résultats sont réglés par le workflow V14 existant. Aucun nouveau SQL n'est nécessaire. Les sélections en attente et annulées sont exclues des ratios. Chaque jambe est comptée une fois par combiné suivi, même si une prédiction identique figure dans plusieurs combinés.
