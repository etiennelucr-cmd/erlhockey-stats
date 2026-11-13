# ErlHockey V24.1 — Vérification du bilan NHL Picks

Cette archive contient le bilan automatique global, le bilan certifié, les archives non certifiées et les choix personnels.

**Vérification de déploiement :** dans NHL Picks, sous le titre « Prédictions automatiques · Bilan et suivi », la mention « Version du bilan : V24.1 » doit apparaître. Si elle est absente, Streamlit utilise une ancienne version de `auto_dashboard_v21.py` ou un ancien déploiement.

Le panneau « Diagnostic du bilan V24.1 » affiche les statuts réellement lus depuis Supabase.

Les lignes `v21_auto_picks` ne sont ni modifiées ni recertifiées. Les résultats en attente et annulés sont exclus du dénominateur de réussite.

**Installation :** remplacer les fichiers sur la branche déployée puis redémarrer l'application Streamlit. Aucun SQL supplémentaire.
