-- A executer UNE FOIS dans Supabase SQL Editor AVANT le deploiement V21.3.
-- Aucun ancien pick n'est supprime ou modifie : ils restent non certifies.
ALTER TABLE public.v21_auto_picks
    ADD COLUMN IF NOT EXISTS validation_state text NOT NULL DEFAULT 'legacy_unverified',
    ADD COLUMN IF NOT EXISTS validation_version text,
    ADD COLUMN IF NOT EXISTS validation_note text;

-- Historique auditable, uniquement les nouveaux picks verifies sont certifies.
CREATE INDEX IF NOT EXISTS v21_auto_picks_validation_idx
    ON public.v21_auto_picks(validation_state, profile, status);

-- Requete de verification apres installation :
SELECT validation_state, COALESCE(validation_version, 'ancienne version') AS version,
       status, COUNT(*) AS nombre
FROM public.v21_auto_picks
GROUP BY validation_state, validation_version, status
ORDER BY validation_state, version, status;
