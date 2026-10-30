# ErlHockey V17 — filtre de disponibilité

## Important : source des statuts
Cette version ne récupère **pas** automatiquement les blessures NHL. Le fichier `player_availability_v17.csv` doit être mis à jour par un opérateur à partir d'une source de confiance. Sans cette mise à jour, le mode strict (activé par défaut) ne proposera **aucun joueur** dans le Combo Builder ou NHL Picks. C'est volontaire pour ne pas présenter un joueur comme disponible sans preuve.

## Format
Colonnes : `player_name,team,status,checked_at_utc`.

- `player_name` : nom exact figurant dans ErlHockey ; `team` : abréviation NHL (EDM, TOR, etc.).
- `status` : `confirmed` / `active` / `available` / `playing` pour une présence vérifiée ; `out`, `injured`, `ir`, `ltir`, `suspended`, `day-to-day`, `gtd`, `questionable`, `doubtful`, `scratched` pour exclure.
- `checked_at_utc` : date/heure UTC ISO 8601 avec fuseau, par exemple `2026-10-30T15:00:00Z` (exemple de format uniquement).
- Les statuts de plus de 24 heures, les dates sans fuseau et les statuts inconnus sont considérés non vérifiés.

Un exemple fictif (NE PAS copier comme donnée réelle) : `Example Player,EDM,confirmed,2026-10-30T15:00:00Z`.

## Installation
Téléverser tous les fichiers dans GitHub en préservant les dossiers. Renseigner le CSV avant d'utiliser les prédictions joueurs. Aucun SQL supplémentaire. Les combinés déjà enregistrés dans Supabase ne sont pas modifiés. Le filtre de joueurs ne corrige pas les prédictions de matchs : elles ne tiennent toujours pas compte des absences.

## Limites
Les confirmations peuvent changer après la vérification ; contrôler les compositions avant les rencontres. Le mode permissif du Combo Builder est facultatif et affiche un avertissement pour les joueurs non confirmés. NHL Picks reste strict. Aucun statut de santé n'est inféré des performances passées.
