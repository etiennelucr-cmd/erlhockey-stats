# ErlHockey V15 — interface épurée et résultats

## Modifications
- Navigation réduite à Tableau de bord, Points 5/5, Betting Center, Combo Builder, Mes combinés et NHL Picks.
- Tableau de bord : bilans des combinés suivis, résultats individuels gagnés/perdus et dernières sélections à partir des tables V14.
- Points 5/5 : joueurs en 5/5 uniquement si leur équipe joue aujourd'hui ou demain (heure de Paris), avant le coup d'envoi.
- NHL Picks : historique des buts match par match et fréquences de matchs avec au moins un point/but sur les 5 derniers matchs.
- Le suivi Supabase V14 et les workflows existants sont conservés.

## Déploiement
Déployer les fichiers du dossier `erlhockey-stats-main` sur une branche GitHub de test en conservant les chemins, secrets et configurations Streamlit. Ne pas téléverser le dossier parent comme sous-dossier supplémentaire. Aucun changement SQL nécessaire. Tester les pages avec les données réelles avant fusion.

## Limites
Les pourcentages Points/Buts de NHL Picks sont des fréquences historiques sur 5 matchs, pas des probabilités calibrées. Le tableau de bord affiche les statuts enregistrés par le script de vérification V14 ; les matchs non réglés restent en attente. La collecte NHL doit être à jour.
