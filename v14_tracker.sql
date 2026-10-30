-- Exécuter une fois dans l'éditeur SQL Supabase. Tables privées : ne pas exposer via l'API publique.
CREATE TABLE IF NOT EXISTS tracked_combos (
 id BIGSERIAL PRIMARY KEY,
 profile TEXT NOT NULL,
 signature TEXT NOT NULL UNIQUE,
 theoretical_probability DOUBLE PRECISION NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','won','lost','void'))
);
CREATE TABLE IF NOT EXISTS tracked_legs (
 id BIGSERIAL PRIMARY KEY,
 combo_id BIGINT NOT NULL REFERENCES tracked_combos(id) ON DELETE CASCADE,
 game_id BIGINT NOT NULL REFERENCES nhl_games(game_id),
 match_label TEXT NOT NULL,
 selection TEXT NOT NULL,
 market TEXT NOT NULL,
 probability DOUBLE PRECISION NOT NULL,
 kickoff TIMESTAMPTZ NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','won','lost','void')),
 UNIQUE(combo_id,game_id)
);
CREATE INDEX IF NOT EXISTS tracked_legs_pending_idx ON tracked_legs(game_id) WHERE status='pending';
CREATE INDEX IF NOT EXISTS tracked_combos_created_idx ON tracked_combos(created_at);
