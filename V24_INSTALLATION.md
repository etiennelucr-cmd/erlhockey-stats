# ErlHockey V24 — cumulative V23 + améliorations 4, 5 et 6

Base : ErlHockey V23 correction du bilan NHL Picks.

- Streaks positifs/négatifs pour le marché, 1+ point et 1+ but. Positif = matchs consécutifs réussis ; négatif = échecs consécutifs.
- Force défensive adverse : buts encaissés par match sur les 10 derniers matchs terminés collectés. Descriptif uniquement ; aucune modification artificielle de la probabilité.
- Fiche enrichie par pick : 5 et 10 matchs, séquence récente, détails adversaire.
- Historique des picks personnels filtrable par statut. Le bilan automatique V23 reste distinct.

Installation : déployer les fichiers du ZIP sur GitHub, redémarrer Streamlit, ouvrir NHL Picks. Aucun nouveau SQL.

Validation : compilation Python réussie. Les tests pytest NHL Picks n'ont pas pu être exécutés dans l'environnement de préparation faute du paquet Streamlit. Aucun test Supabase/Streamlit réel effectué.
