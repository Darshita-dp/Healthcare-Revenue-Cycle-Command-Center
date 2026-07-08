-- ============================================================================
-- create_tables.sql — convenience wrapper
-- ============================================================================
-- The canonical DDL lives in schema.sql (tables, constraints, indexes,
-- comments). This wrapper exists so the standard runbook command works:
--
--   psql -U rcm_user -d revenue_cycle -f database/create_tables.sql
--
-- psql's \i includes schema.sql relative to the client working directory,
-- so run it from the repository root.
-- ============================================================================

\i database/schema.sql

-- Verify all 12 tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE ANY (ARRAY['dim\_%', 'fact\_%'])
ORDER BY table_name;
