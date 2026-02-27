-- Migration 001: Company-first redesign
-- Apply to existing installations upgrading from v0.1.0-aggregator
-- Safe to run multiple times (uses IF NOT EXISTS / IF EXISTS)

-- Add company_id FK to jobs
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES tracked_companies(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_jobs_company_id ON jobs(company_id);
CREATE INDEX IF NOT EXISTS ix_jobs_company_active ON jobs(company_id, is_active, date_posted DESC) WHERE is_active = TRUE;

-- Drop old aggregator table
DROP TABLE IF EXISTS search_configs CASCADE;
