# ErlHockey V21.5 — Filtre blessures ESPN pour les picks automatiques

## Corrections
- Reutilise la collecte existante `espn_injuries_v19.py` et ses tables Supabase ; aucun scraping CBS/DailyFaceoff ajoute.
- Exclut les joueurs signales dans le dernier rapport ESPN, y compris `Day-to-Day` (politique conservatrice).
- Rapproche le nom du joueur (y compris initiale + nom) **et** l'equipe NHL courante verifiee.
- Refuse de creer de nouvelles predictions si le rapport ESPN est absent, vide ou vieux de plus de 24 h. Le script indique de lancer le workflow ESPN.
- Regle d'abord les matchs termines, meme si le controle blessures echoue ensuite. Les picks historiques restent intacts.
- Marque les nouvelles predictions `roster_injury_checked` / `V21.5` dans Supabase.

## Installation
1. Verifier que `V21_3_MIGRATION.sql` a deja ete execute dans Supabase.
2. Dans GitHub, remplacer `auto_picks_v21.py` par celui de V21.5. Conserver `espn_injuries_v19.py` et le workflow `.github/workflows/blessures-espn-v19.yml` existants.
3. GitHub Actions -> **Blessures NHL ESPN V19** -> **Run workflow**. Attendre un succes et un nombre de blessures enregistre.
4. GitHub Actions -> **V21 Predictions automatiques** -> **Run workflow**.
5. Lire les journaux. Si 0 ajout et doublons ignores, c'est normal pour les matchs deja enregistres.

## Controle SQL
```sql
SELECT last_success_at, count, error FROM nhl_injury_sync_v19 WHERE id=1;
SELECT validation_version,validation_state,status,COUNT(*)
FROM v21_auto_picks GROUP BY 1,2,3 ORDER BY 1,2,3;
```

## Limites
- ESPN peut etre indisponible, changer son format ou contenir des informations incompletes. CBS et Daily Faceoff restent des sources de verification **manuelle**, non integrees automatiquement.
- L'absence de signalement de blessure ne prouve pas que le joueur est aligne.
- Un joueur `Day-to-Day` est exclu par prudence, meme s'il peut finalement jouer.
- Les 35 anciens picks ne sont ni modifies ni certifies retroactivement.
- Le fonctionnement avec les services externes doit etre valide sur GitHub.
