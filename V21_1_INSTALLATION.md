# ErlHockey V21.1 — contrôle des effectifs NHL

## Changement
`auto_picks_v21.py` récupère les effectifs officiels actuels via `https://api-web.nhle.com/v1/roster/{TEAM}/current` et vérifie l'identifiant NHL du joueur contre son équipe avant de générer un pick. Un effectif indisponible arrête le processus (pas de génération non vérifiée). Les historiques restent filtrés par la dernière équipe observée : ce contrôle est volontairement conservateur, et peut exclure un joueur récemment transféré jusqu'à l'arrivée de nouvelles statistiques sous sa nouvelle équipe.

## Installation
Remplacer `auto_picks_v21.py` à la racine du dépôt et conserver le workflow V21 existant. Aucun changement SQL n'est nécessaire. Exécuter le workflow manuellement puis vérifier les logs et `v21_auto_picks`.

## ATTENTION — 35 anciens picks
Les 35 prédictions V21 déjà enregistrées ne sont **pas** modifiées ni effacées automatiquement. Leur fiabilité d'association joueur/match n'est pas garantie. Ne pas les utiliser pour juger la performance du moteur corrigé sans audit préalable. La contrainte UNIQUE(profile,game_id) empêche la régénération des mêmes matchs, même après installation de V21.1. Pour un suivi propre, laisser les anciens enregistrements à part ou les auditer et les exclure de l'analyse V21.1; ne pas les supprimer sans sauvegarde.

## Limites
Un joueur sur l'effectif officiel peut être blessé, non aligné ou absent du match. Les prédictions restent non calibrées. Cette correction ne garantit ni la participation ni la rentabilité.
