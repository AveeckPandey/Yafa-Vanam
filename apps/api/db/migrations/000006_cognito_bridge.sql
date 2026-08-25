-- Cognito identity bridge: links a verified AWS Cognito sign-in (by its stable
-- `sub` claim) to the local users row so POST /auth/cognito/exchange can issue
-- first-party session cookies after validating an id_token.
ALTER TABLE users ADD COLUMN IF NOT EXISTS cognito_subject TEXT UNIQUE;
