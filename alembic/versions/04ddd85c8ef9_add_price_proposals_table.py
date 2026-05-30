"""add price proposals table

Revision ID: 04ddd85c8ef9
Revises: e0fd55fcb6de
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '04ddd85c8ef9'
down_revision = 'e0fd55fcb6de'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'price_proposals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('rider_id', sa.Integer(), nullable=False),
        sa.Column('proposed_price', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rider_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_price_proposals_order_id', 'price_proposals', ['order_id'])
    op.create_index('ix_price_proposals_rider_id', 'price_proposals', ['rider_id'])

def downgrade() -> None:
    op.drop_index('ix_price_proposals_rider_id', 'price_proposals')
    op.drop_index('ix_price_proposals_order_id', 'price_proposals')
    op.drop_table('price_proposals')
