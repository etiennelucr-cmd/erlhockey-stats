# ErlHockey V20 — première livraison

## Inclus
- `combo_v20.py` : classement des combinés par produit décroissant des probabilités estimées, dans les bandes des cinq profils existants.
- `app.py` importe la nouvelle interface V20 ; l'interface Streamlit existante reste conservée.
- `tests/test_combo_v20.py` : tests unitaires pour classement, unicité des matchs, probabilités invalides, manque de matchs et ordre des résultats.

## Installation
Installer les dépendances existantes : `pip install -r requirements.txt`, puis `streamlit run app.py` avec la configuration Supabase habituelle.
Lancer les tests : `python -m unittest discover -s tests -v`.

## Limites importantes
- Les probabilités proviennent toujours des estimateurs V12 ; aucune calibration ou backtest historique n'est inclus.
- Le produit des probabilités suppose l'indépendance entre matchs.
- Les marchés 60 minutes restent classés `void` par `settle_v14.py` car le schéma actuel ne fournit pas le score réglementaire séparé ; aucune victoire/défaite n'est inventée.
- Les marchés de total et les règles bookmaker ne sont pas harmonisés.
- La diversité des marchés ne départage que des combinés de probabilité identique, elle ne remplace pas l'objectif de probabilité maximale.
- L'application complète n'a pas été exécutée contre Supabase dans cet environnement.

## Étapes suivantes pour une V20 complète
1. Stocker le score à 60 minutes et définir les règles de règlement par marché.
2. Journaliser chaque prédiction horodatée avant match et sa version de modèle.
3. Effectuer un backtest chronologique hors échantillon et mesurer Brier/log-loss/calibration.
4. Tester des modèles tenant compte des gardiens, du temps de glace et des adversaires.
5. Modéliser les dépendances et intégrer les cotes seulement après validation.

## NHL Picks V20 — cinq profils
- `nhl_picks_v20.py` génère des suggestions joueurs par profil, sur 10 matchs maximum, avec lissage Beta(1,1) non calibré.
- Les suggestions peuvent être suivies individuellement via `tracked_combos` et `tracked_legs` existants (aucune migration nécessaire).
- Le suivi ne crée aucune mise et ne calcule aucun ROI sans cotes/mises.
- Les prédictions non suivies ne sont pas historisées ; les résultats du bilan sont ceux des picks suivis uniquement.
- L'exécution de `settle_v14.py` après la collecte est nécessaire pour régler les résultats.

### V20 — Un pick par rencontre et par profil
NHL Picks propose désormais un pick pour chaque rencontre éligible dans chaque profil, sans limite fixe de cinq picks. Par exemple, sept rencontres éligibles produisent sept suggestions par profil. Le moteur privilégie des joueurs distincts entre profils pour une même rencontre quand les données le permettent. En cas de manque de candidats dans la plage de probabilité d'un profil, un pick de remplacement est signalé « Hors plage du profil ». Les probabilités demeurent exploratoires, non calibrées. Les picks restent enregistrés uniquement sur action « Suivre ce pick ».

### V20 — Filtre des dates NHL Picks
Dans NHL Picks, choisir **Ce soir**, **Demain** ou **Mixte**. Les journées sont définies en fuseau Europe/Paris, et seuls les matchs encore à venir sont proposés. Le choix s'applique aux cinq profils, à leurs cases individuelles et au bouton All. Le bilan historique reste cumulatif et ne dépend pas du filtre de dates.
