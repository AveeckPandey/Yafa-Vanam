-- The deterministic YAFA shade-analysis flow was retired in favor of the
-- separate, stateless product-knowledge RAG service. These tables have no
-- remaining application readers or writers.
DROP TABLE IF EXISTS user_shade_history CASCADE;
DROP TABLE IF EXISTS user_beauty_profiles CASCADE;
DROP TABLE IF EXISTS yafa_sessions CASCADE;
