# Combo Builder V12 — ajout

- Nouvelle page `🧩 Combo Builder V12` dans Streamlit.
- Fenêtre : aujourd'hui et demain en dates civiles `Europe/Paris`, seulement matchs futurs.
- Quatre sélections issues de quatre `game_id` distincts, top 3 exploratoire.
- Marchés actifs : 1+ point, 2+ points, 1+ but, total buts over/under 4,5/5,5/6,5.
- Marché tirs : **non disponible**, car `nhl_player_games` n'enregistre pas les tirs.
- Marché vainqueur : **non disponible**, car aucun modèle calibré ne le justifie.
- Modèle joueur : moyenne Beta(1,1) sur 5/10/20 matchs ; matchs : Poisson simple.
- Les streaks sont calculés du match le plus récent vers le plus ancien, sans confondre fréquence et série.
- Aucun schéma Supabase ni secret supplémentaire requis.
- Les estimations ne sont pas validées et ne permettent pas d'affirmer qu'un combiné est rentable.
- Les joueurs sont associés à leur dernière équipe enregistrée ; les transferts, blessures et compositions ne sont pas vérifiés.
- Le classement équilibré privilégie ici la probabilité faute de cotes, et non la value.
- Pour obtenir de vraies analyses tirs, enrichir le collecteur et la table avec les tirs par match.

## Déploiement

Créer une branche GitHub de test, copier `app.py` et `combo_v12.py`, conserver `betting_v12.py`, puis vérifier Streamlit avec une base Supabase de test. Ne pas remplacer directement la version de production.
