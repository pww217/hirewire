-- Migration 003: Add included_keywords to user_settings
-- Idempotent: safe to run multiple times

ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS included_keywords TEXT[] DEFAULT '{}';
