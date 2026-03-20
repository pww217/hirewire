"""drop excluded_companies from user_settings

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-19 00:00:00.000000

Changes:
- Drop user_settings.excluded_companies (added in baseline, never used by ORM or API)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('user_settings', 'excluded_companies', if_exists=True)


def downgrade() -> None:
    op.add_column('user_settings', sa.Column(
        'excluded_companies', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False
    ))
