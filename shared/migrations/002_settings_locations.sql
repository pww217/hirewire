-- Migration 002: Replace excluded_companies with preferred_locations in user_settings
-- Idempotent: safe to run multiple times

ALTER TABLE user_settings DROP COLUMN IF EXISTS excluded_companies;

ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS preferred_locations TEXT[] DEFAULT '{}';
