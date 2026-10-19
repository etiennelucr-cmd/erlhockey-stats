# ErlHockey Stats V1 🏒

Prototype Streamlit NHL, indépendant du bot Telegram et de Mi Español.

## Démarrer sur Windows

1. Décompresser le ZIP.
2. Ouvrir le dossier `erlhockey_stats_v1`.
3. Taper `cmd` dans la barre d'adresse de l'Explorateur Windows.
4. Exécuter :

```bat
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Le navigateur s'ouvre normalement sur http://localhost:8501.

## Déploiement

Créer un dépôt GitHub distinct, y ajouter les fichiers du dossier, puis déployer `app.py` via Streamlit Community Cloud. Aucune clé API ni fichier `.env` nécessaire pour cette V1.

## Limites importantes

- Les données proviennent des API publiques NHL, sous réserve de disponibilité.
- Les listes de joueurs proviennent des classements NHL (leaders) et ne couvrent pas forcément tous les joueurs.
- Les pages 24 h et séries utilisent des approximations documentées ; elles ne doivent pas être interprétées comme un scan exhaustif.
- La collecte 24 h/24, Supabase, l'historique persistant et Telegram **ne sont pas encore connectés**.
- Ne jamais mettre un `.env`, un token Telegram ou un fichier `secrets.toml` dans GitHub.
- Les anciens jetons partagés doivent être révoqués et remplacés.
