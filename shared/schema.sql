-- ============================================================================
-- HireWire Database Schema
-- ============================================================================
-- CONVENTIONS:
-- - All timestamps are UTC (TIMESTAMPTZ)
-- - VARCHAR limits match Pydantic model validators
-- ============================================================================

-- ============================================================================
-- TRACKED COMPANIES TABLE - Companies to poll via ATS APIs
-- ============================================================================
CREATE TABLE tracked_companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    website VARCHAR(500),
    ats_type VARCHAR(50),              -- 'greenhouse', 'lever', 'ashby'
    ats_identifier VARCHAR(255),       -- Company slug for ATS API
    last_scraped TIMESTAMPTZ,
    job_count INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Glassdoor ratings (cached, refreshed weekly)
    glassdoor_id INTEGER,
    glassdoor_rating DECIMAL(2,1),     -- e.g. 4.2 out of 5.0
    glassdoor_url VARCHAR(500),
    rating_updated_at TIMESTAMPTZ
);

CREATE INDEX ix_tracked_companies_ats_type ON tracked_companies(ats_type);
CREATE INDEX ix_tracked_companies_enabled ON tracked_companies(enabled) WHERE enabled = TRUE;

-- ============================================================================
-- JOBS TABLE - Core job listings
-- ============================================================================
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    dedup_hash VARCHAR(32) NOT NULL UNIQUE,

    -- Source company (FK to tracked_companies)
    company_id INTEGER REFERENCES tracked_companies(id) ON DELETE SET NULL,

    -- Core fields
    title VARCHAR(500) NOT NULL,
    company VARCHAR(255) NOT NULL,
    company_url VARCHAR(500),

    -- Location (normalized)
    location_raw VARCHAR(255),
    location_city VARCHAR(100),
    location_state VARCHAR(100),
    location_country VARCHAR(100) DEFAULT 'USA',
    is_remote BOOLEAN DEFAULT FALSE,

    -- Job details
    description TEXT,
    job_url VARCHAR(1000) NOT NULL,
    job_type VARCHAR(50),  -- 'full_time', 'part_time', 'contract', 'internship'

    -- Salary (normalized to yearly)
    salary_min DECIMAL(12, 2),
    salary_max DECIMAL(12, 2),
    salary_interval VARCHAR(20) DEFAULT 'yearly',  -- 'yearly', 'monthly', 'weekly', 'daily', 'hourly'

    -- Dates
    date_posted TIMESTAMPTZ,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),

    -- Company metadata (available from some sources)
    company_size VARCHAR(50),
    company_industry VARCHAR(100),

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Full-text search vector
    search_vector TSVECTOR
);

-- Indexes for jobs table
CREATE INDEX ix_jobs_dedup_hash ON jobs(dedup_hash);
CREATE INDEX ix_jobs_company_id ON jobs(company_id);
CREATE INDEX ix_jobs_date_posted ON jobs(date_posted DESC);
CREATE INDEX ix_jobs_first_seen ON jobs(first_seen DESC);
CREATE INDEX ix_jobs_company ON jobs(company);
CREATE INDEX ix_jobs_location ON jobs(location_city, location_state);
CREATE INDEX ix_jobs_is_remote ON jobs(is_remote) WHERE is_remote = TRUE;
CREATE INDEX ix_jobs_is_active ON jobs(is_active) WHERE is_active = TRUE;
CREATE INDEX ix_jobs_search_vector ON jobs USING GIN(search_vector);

-- Composite indexes for common query patterns
CREATE INDEX ix_jobs_active_posted ON jobs(is_active, date_posted DESC)
    WHERE is_active = TRUE;
CREATE INDEX ix_jobs_company_active ON jobs(company_id, is_active, date_posted DESC)
    WHERE is_active = TRUE;

-- ============================================================================
-- JOB SOURCES TABLE - Track where each job was found
-- ============================================================================
CREATE TABLE job_sources (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,       -- 'greenhouse', 'lever', 'ashby'
    source_site VARCHAR(50),           -- same as source for ATS scrapers
    external_id VARCHAR(255),          -- Source's unique ID for the job
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_job_sources_job_id ON job_sources(job_id);
CREATE INDEX ix_job_sources_source ON job_sources(source);
CREATE UNIQUE INDEX ix_job_sources_unique ON job_sources(job_id, source, source_site);

-- ============================================================================
-- USER JOB STATE TABLE - Favorites and hidden jobs
-- ============================================================================
CREATE TABLE user_job_state (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    is_favorite BOOLEAN DEFAULT FALSE,
    is_hidden BOOLEAN DEFAULT FALSE,
    is_seen BOOLEAN DEFAULT FALSE,
    favorited_at TIMESTAMPTZ,
    hidden_at TIMESTAMPTZ,
    seen_at TIMESTAMPTZ
);

CREATE INDEX ix_user_job_state_job_id ON user_job_state(job_id);
CREATE INDEX ix_user_job_state_favorite ON user_job_state(is_favorite) WHERE is_favorite = TRUE;
CREATE INDEX ix_user_job_state_hidden ON user_job_state(is_hidden) WHERE is_hidden = TRUE;
CREATE INDEX ix_user_job_state_seen ON user_job_state(is_seen) WHERE is_seen = FALSE;

-- ============================================================================
-- APPLICATIONS TABLE - Track application status
-- ============================================================================
CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'applied',  -- 'applied', 'interviewing', 'rejected', 'offer'
    notes TEXT,
    applied_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_applications_job_id ON applications(job_id);
CREATE INDEX ix_applications_status ON applications(status);

-- ============================================================================
-- USER SETTINGS TABLE - Global user preferences
-- ============================================================================
CREATE TABLE user_settings (
    id SERIAL PRIMARY KEY,
    preferred_locations TEXT[] DEFAULT '{}',
    title_keywords TEXT[] DEFAULT '{}',
    description_keywords TEXT[] DEFAULT '{}',
    excluded_keywords TEXT[] DEFAULT '{}',
    default_location VARCHAR(255),
    default_remote BOOLEAN DEFAULT FALSE,
    posted_after VARCHAR(20),
    min_glassdoor_rating INTEGER,
    job_type VARCHAR(50),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default settings row
INSERT INTO user_settings (id) VALUES (1);

-- ============================================================================
-- FULL-TEXT SEARCH TRIGGER
-- ============================================================================
CREATE OR REPLACE FUNCTION update_job_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.company, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER job_search_vector_update
    BEFORE INSERT OR UPDATE OF title, company, description ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_job_search_vector();
