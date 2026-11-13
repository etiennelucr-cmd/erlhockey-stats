# Correctif bilan NHL Picks V23

- Toutes les lignes de `v21_auto_picks` sont incluses dans le bilan automatique global.
- Les picks historiques non certifiés apparaissent dans une catégorie séparée.
- La certification technique reconnaît `roster_verified` et `roster_injury_checked` si `validation_version` est renseignée. Cette certification ne prouve pas une présence dans l'alignement officiel.
- Les choix personnels `tracked_legs` restent séparés.
- Le taux de réussite est gagné / (gagné + perdu). Les `pending` et `void` n'entrent pas dans le dénominateur.
- Aucun changement SQL, aucune mise à jour des lignes historiques.

Installation : déposer les fichiers sur GitHub puis redémarrer Streamlit. Vérifier que le total automatique est non nul et que les profils concordent avec l'historique.
