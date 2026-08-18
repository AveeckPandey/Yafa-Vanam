-- Authentication identities and the BCrypt credentials used by the Go auth service.
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_subject TEXT UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
