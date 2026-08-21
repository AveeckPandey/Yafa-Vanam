CREATE TABLE yafa_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    anonymous_token_hash BYTEA,
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
    selfie_storage_key TEXT,
    confirmed_shade_id UUID REFERENCES shades(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'analyzed', 'confirmed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    analyzed_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    CHECK ((user_id IS NOT NULL) OR (anonymous_token_hash IS NOT NULL))
);

CREATE TABLE user_beauty_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    confirmed_shade_id UUID REFERENCES shades(id) ON DELETE SET NULL,
    yafa_answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_shade_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shade_id UUID NOT NULL REFERENCES shades(id) ON DELETE RESTRICT,
    yafa_session_id UUID NOT NULL UNIQUE REFERENCES yafa_sessions(id) ON DELETE RESTRICT,
    source TEXT NOT NULL DEFAULT 'yafa_confirmed' CHECK (source = 'yafa_confirmed'),
    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_yafa_sessions_user_started ON yafa_sessions(user_id, started_at DESC) WHERE user_id IS NOT NULL;
CREATE INDEX idx_yafa_sessions_status ON yafa_sessions(status);
