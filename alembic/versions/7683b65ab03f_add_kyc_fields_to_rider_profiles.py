"""add kyc fields to rider_profiles
Revision ID: 7683b65ab03f
Revises: 6c6cfe0d4f82
Create Date: 2026-05-09 21:18:15.920633
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7683b65ab03f'
down_revision: Union[str, Sequence[str], None] = '6c6cfe0d4f82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('rider_profiles', sa.Column('kyc_status', sa.String(30), nullable=False, server_default='pending'))
    op.add_column('rider_profiles', sa.Column('cni_front_url', sa.String(), nullable=True))
    op.add_column('rider_profiles', sa.Column('cni_back_url', sa.String(), nullable=True))
    op.add_column('rider_profiles', sa.Column('selfie_url', sa.String(), nullable=True))
    op.add_column('rider_profiles', sa.Column('permis_url', sa.String(), nullable=True))
    op.add_column('rider_profiles', sa.Column('kyc_rejection_reason', sa.String(255), nullable=True))
    op.add_column('rider_profiles', sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default='false'))

def downgrade() -> None:
    op.drop_column('rider_profiles', 'is_blocked')
    op.drop_column('rider_profiles', 'kyc_rejection_reason')
    op.drop_column('rider_profiles', 'permis_url')
    op.drop_column('rider_profiles', 'selfie_url')
    op.drop_column('rider_profiles', 'cni_back_url')
    op.drop_column('rider_profiles', 'cni_front_url')
    op.drop_column('rider_profiles', 'kyc_status')
