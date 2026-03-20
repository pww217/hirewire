"""baseline schema

Revision ID: e39303dba4ed
Revises:
Create Date: 2026-03-12 16:41:55.283936

This is the initial migration representing the full schema for fresh installs.
Existing databases created via docker-entrypoint-initdb.d or schema.sql
should be stamped at this revision:

    alembic stamp e39303dba4ed

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e39303dba4ed'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tracked_companies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('ats_type', sa.String(50), nullable=True),
        sa.Column('ats_identifier', sa.String(255), nullable=True),
        sa.Column('last_scraped', sa.DateTime(timezone=True), nullable=True),
        sa.Column('job_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('glassdoor_id', sa.Integer(), nullable=True),
        sa.Column('glassdoor_rating', sa.Numeric(2, 1), nullable=True),
        sa.Column('glassdoor_url', sa.String(500), nullable=True),
        sa.Column('rating_updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_tracked_companies_ats_type', 'tracked_companies', ['ats_type'])
    op.create_index('ix_tracked_companies_enabled', 'tracked_companies', ['enabled'],
                    postgresql_where=sa.text('enabled = TRUE'))

    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('dedup_hash', sa.String(32), nullable=False, unique=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('tracked_companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('company_url', sa.String(500), nullable=True),
        sa.Column('location_raw', sa.String(255), nullable=True),
        sa.Column('location_city', sa.String(100), nullable=True),
        sa.Column('location_state', sa.String(100), nullable=True),
        sa.Column('location_country', sa.String(100), nullable=True, server_default="'USA'"),
        sa.Column('is_remote', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('job_url', sa.String(1000), nullable=False),
        sa.Column('job_type', sa.String(50), nullable=True),
        sa.Column('salary_min', sa.Numeric(12, 2), nullable=True),
        sa.Column('salary_max', sa.Numeric(12, 2), nullable=True),
        sa.Column('salary_interval', sa.String(20), nullable=True, server_default="'yearly'"),
        sa.Column('date_posted', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('company_size', sa.String(50), nullable=True),
        sa.Column('company_industry', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    )
    op.create_index('ix_jobs_dedup_hash', 'jobs', ['dedup_hash'])
    op.create_index('ix_jobs_company_id', 'jobs', ['company_id'])
    op.create_index('ix_jobs_date_posted', 'jobs', ['date_posted'],
                    postgresql_ops={'date_posted': 'DESC'})
    op.create_index('ix_jobs_first_seen', 'jobs', ['first_seen'],
                    postgresql_ops={'first_seen': 'DESC'})
    op.create_index('ix_jobs_company', 'jobs', ['company'])
    op.create_index('ix_jobs_location', 'jobs', ['location_city', 'location_state'])
    op.create_index('ix_jobs_is_remote', 'jobs', ['is_remote'],
                    postgresql_where=sa.text('is_remote = TRUE'))
    op.create_index('ix_jobs_is_active', 'jobs', ['is_active'],
                    postgresql_where=sa.text('is_active = TRUE'))
    op.create_index('ix_jobs_search_vector', 'jobs', ['search_vector'],
                    postgresql_using='gin')
    op.create_index('ix_jobs_active_posted', 'jobs', ['is_active', 'date_posted'],
                    postgresql_where=sa.text('is_active = TRUE'))
    op.create_index('ix_jobs_company_active', 'jobs', ['company_id', 'is_active', 'date_posted'],
                    postgresql_where=sa.text('is_active = TRUE'))

    op.create_table(
        'job_sources',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_site', sa.String(50), nullable=True),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('job_id', 'source', 'source_site', name='ix_job_sources_unique'),
    )
    op.create_index('ix_job_sources_job_id', 'job_sources', ['job_id'])
    op.create_index('ix_job_sources_source', 'job_sources', ['source'])

    op.create_table(
        'user_job_state',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_seen', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('favorited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hidden_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('seen_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_user_job_state_job_id', 'user_job_state', ['job_id'])
    op.create_index('ix_user_job_state_favorite', 'user_job_state', ['is_favorite'],
                    postgresql_where=sa.text('is_favorite = TRUE'))
    op.create_index('ix_user_job_state_hidden', 'user_job_state', ['is_hidden'],
                    postgresql_where=sa.text('is_hidden = TRUE'))
    op.create_index('ix_user_job_state_seen', 'user_job_state', ['is_seen'],
                    postgresql_where=sa.text('is_seen = FALSE'))

    op.create_table(
        'applications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('status', sa.String(50), nullable=False, server_default="'applied'"),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_applications_job_id', 'applications', ['job_id'])
    op.create_index('ix_applications_status', 'applications', ['status'])

    op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('excluded_companies', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('excluded_keywords', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('preferred_locations', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('included_keywords', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('default_location', sa.String(255), nullable=True),
        sa.Column('default_remote', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # FTS trigger function and trigger
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_job_search_vector() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.company, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    op.execute(sa.text("""
        DROP TRIGGER IF EXISTS job_search_vector_update ON jobs;
    """))
    op.execute(sa.text("""
        CREATE TRIGGER job_search_vector_update
            BEFORE INSERT OR UPDATE OF title, company, description ON jobs
            FOR EACH ROW EXECUTE FUNCTION update_job_search_vector();
    """))

    # Default user settings row
    op.execute(sa.text(
        "INSERT INTO user_settings (id) VALUES (1) ON CONFLICT DO NOTHING"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS job_search_vector_update ON jobs"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS update_job_search_vector"))
    op.drop_table('applications')
    op.drop_table('user_settings')
    op.drop_table('user_job_state')
    op.drop_table('job_sources')
    op.drop_table('jobs')
    op.drop_table('tracked_companies')
