-- Run once in Supabase SQL editor. Automatic predictions are separate from user picks.
CREATE TABLE IF NOT EXISTS v21_auto_picks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    profile text NOT NULL CHECK (profile IN ('Prudent','Modéré','Équilibré','Risqué','Ultra risqué')),
    game_id bigint NOT NULL,
    player_id text NOT NULL,
    match_label text NOT NULL,
    selection text NOT NULL,
    market text NOT NULL,
    probability double precision NOT NULL CHECK (probability >= 0 AND probability <= 1),
    kickoff timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','won','lost','void')),
    UNIQUE(profile,game_id),
    CHECK (created_at < kickoff)
);
CREATE INDEX IF NOT EXISTS v21_auto_picks_created_idx ON v21_auto_picks(created_at DESC);
