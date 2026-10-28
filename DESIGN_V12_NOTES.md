# ErlHockey V12 — Intégration du design

## Modifications
- Thème sombre bleu électrique dans `theme_v12.css` (chargé par `app.py`).
- En-tête cohérent avec horloge Europe/Paris, bannière dynamique selon la page.
- Amélioration visuelle des tableaux, métriques, onglets, boutons et barre latérale.
- Mise en page responsive et aucune dépendance ajoutée.
- Les calculs de paris, filtres, données Supabase et workflows sont inchangés.

## Déploiement
1. Tester sur une branche GitHub ou un environnement Streamlit de préproduction.
2. Copier **app.py** et **theme_v12.css** ensemble (et conserver tous les autres fichiers du ZIP).
3. Redémarrer Streamlit et vérifier Betting Center et Combo Builder avec les secrets Supabase habituels.

## Limites
La maquette illustrée dans le chat était conceptuelle : ce thème reprend sa direction graphique mais ne reproduit pas exactement ses cartes/logos. Aucun accès à Supabase n'a été effectué ici. Les prédictions demeurent expérimentales, les tirs cadrés et la victoire ne sont pas entièrement implémentés.
