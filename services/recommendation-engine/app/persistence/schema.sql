-- PostgreSQL production schema. Raw selfies are deliberately absent.
CREATE TABLE IF NOT EXISTS user_beauty_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id TEXT UNIQUE NOT NULL,
  confirmed_shade_code TEXT, confirmed_shade_source TEXT,
  estimated_depth_family TEXT, estimated_undertone TEXT,
  lab_l DOUBLE PRECISION, lab_a DOUBLE PRECISION, lab_b DOUBLE PRECISION, ita DOUBLE PRECISION,
  cv_confidence DOUBLE PRECISION, skin_types JSONB NOT NULL DEFAULT '[]', concerns JSONB NOT NULL DEFAULT '[]',
  preferred_coverage TEXT, preferred_finish TEXT, preferred_intensity TEXT,
  user_confirmed BOOLEAN NOT NULL DEFAULT FALSE, profile_json JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS skin_analysis_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id TEXT NOT NULL,
  predicted_shade_code TEXT, candidate_1 TEXT, candidate_2 TEXT, candidate_3 TEXT,
  lab_l DOUBLE PRECISION, lab_a DOUBLE PRECISION, lab_b DOUBLE PRECISION, ita DOUBLE PRECISION,
  confidence DOUBLE PRECISION, source TEXT, selected_shade_code TEXT, was_corrected BOOLEAN NOT NULL DEFAULT FALSE,
  event_json JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
