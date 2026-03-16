"""split keywords and persist filters in user_settings

Revision ID: a1b2c3d4e5f6
Revises: e39303dba4ed
Create Date: 2026-03-16 00:00:00.000000

Changes:
- Rename user_settings.included_keywords -> title_keywords
- Add user_settings.description_keywords (TEXT[])
- Add user_settings.posted_after (VARCHAR(20))
- Add user_settings.min_glassdoor_rating (INTEGER)
- Add user_settings.job_type (VARCHAR(50))
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e39303dba4ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename included_keywords -> title_keywords
    op.alter_column('user_settings', 'included_keywords', new_column_name='title_keywords')

    # Add new columns
    op.add_column('user_settings', sa.Column(
        'description_keywords', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False
    ))
    op.add_column('user_settings', sa.Column(
        'posted_after', sa.String(20), nullable=True
    ))
    op.add_column('user_settings', sa.Column(
        'min_glassdoor_rating', sa.Integer(), nullable=True
    ))
    op.add_column('user_settings', sa.Column(
        'job_type', sa.String(50), nullable=True
    ))


def downgrade() -> None:
    op.drop_column('user_settings', 'job_type')
    op.drop_column('user_settings', 'min_glassdoor_rating')
    op.drop_column('user_settings', 'posted_after')
    op.drop_column('user_settings', 'description_keywords')
    op.alter_column('user_settings', 'title_keywords', new_column_name='included_keywords')
