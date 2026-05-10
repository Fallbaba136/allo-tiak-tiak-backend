"""add kyc fields to rider_profiles
Revision ID: 7683b65ab03f
Revises: 6c6cfe0d4f82
Create Date: 2026-05-09 21:18:15.920633
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '7683b65ab03f'
down_revision: Union[str, Sequence[str], None] = '6c6cfe0d4f82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def column_exists(table, column):
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [c['name'] for c in insp.get_columns(table)]
    return column in columns

def upgrade() -> None:
    cols = [
        ('kyc_status', sa.Column('kyc_status', sa.String(30), nullable=False, server_default='pending')),
        ('cni_front_url', sa.Column('cni_front_url', sa.String(), nullable=True)),
        ('cni_back_url', sa.Column('cni_back_url', sa.String(), nullable=True)),
        ('selfie_url', sa.Column('selfie_url', sa.String(), nullable=True)),
        ('permis_url', sa.Column('permis_url', sa.String(), nullable=True)),
        ('kyc_rejection_reason', sa.Column('kyc_rejection_reason', sa.String(255), nullable=True)),
        ('is_blocked', sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default='false')),
    ]
    for name, col in cols:
        if not column_exists('rider_profiles', name):
            op.add_column('rider_profiles', col)

def downgrade() -> None:
    pass