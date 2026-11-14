"""xizmat filial narxlari (asosiy narxdan farqli bo'lishi mumkin)

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-27 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0044'
down_revision = '0043'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('service_branch_prices',
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('price', sa.Numeric(14, 2), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('price >= 0', name=op.f('ck_service_branch_prices_price_non_negative')),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], name=op.f('fk_service_branch_prices_service_id_services'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_service_branch_prices_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_service_branch_prices')),
    )
    op.create_index(op.f('ix_service_branch_prices_service_id'), 'service_branch_prices', ['service_id'])
    op.create_index(op.f('ix_service_branch_prices_branch_id'), 'service_branch_prices', ['branch_id'])
    op.create_index('uq_service_branch_prices', 'service_branch_prices', ['service_id', 'branch_id'], unique=True)


def downgrade() -> None:
    op.drop_table('service_branch_prices')
