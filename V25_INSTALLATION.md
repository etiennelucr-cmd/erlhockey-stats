# ErlHockey V25 — Couleurs du bilan NHL Picks

Base : V24.1 (bilan vérifiable) + améliorations V24.

Dans **NHL Picks → Prédictions automatiques · Bilan et suivi**, les lignes du tableau sont colorées par origine : bleu (automatique tous), vert (certifié), orange (historique), violet (mes choix).

Aucune migration SQL, aucun changement aux résultats ni aux formules de réussite.

## Installation

Déployer les fichiers sur la branche GitHub utilisée par Streamlit, redémarrer l'application et vérifier la mention `Version du bilan : V25`.

Les couleurs reposent sur pandas Styler et le support de Streamlit pour les DataFrame stylés ; leur rendu exact peut dépendre de la version de Streamlit et du thème.
