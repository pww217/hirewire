"""add excluded_body_keywords to user_settings

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-18 00:00:00.000000

Changes:
- Add user_settings.excluded_body_keywords (TEXT[])
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_settings', sa.Column(
        'excluded_body_keywords', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False
    ))


def downgrade() -> None:
    op.drop_column('user_settings', 'excluded_body_keywords')
