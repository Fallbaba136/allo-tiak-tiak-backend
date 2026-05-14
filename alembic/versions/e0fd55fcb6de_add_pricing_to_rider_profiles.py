"""add pricing to rider_profiles
Revision ID: e0fd55fcb6de
Revises: b4022563c400
Create Date: 2026-05-14 14:42:20.343089
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e0fd55fcb6de'
down_revision: Union[str, Sequence[str], None] = 'b4022563c400'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c['name'] for c in insp.get_columns('rider_profiles')]
    if 'pricing' not in cols:
        op.add_column('rider_profiles', sa.Column('pricing', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('rider_profiles', 'pricing')
