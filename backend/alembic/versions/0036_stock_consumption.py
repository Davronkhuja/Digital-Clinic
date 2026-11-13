"""to'lovda avtomatik sarf: invoices.stock_consumed_at va yetmagan materiallar jurnali (stock_shortages)

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-21 13:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('invoices', sa.Column('stock_consumed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('stock_shortages',
        sa.Column('invoice_id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('qty_missing', sa.Numeric(14, 3), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('qty_missing > 0', name=op.f('ck_stock_shortages_qty_missing_positive')),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_stock_shortages_invoice_id_invoices'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['item_id'], ['stock_items.id'], name=op.f('fk_stock_shortages_item_id_stock_items'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_stock_shortages_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_shortages')),
    )
    op.create_index(op.f('ix_stock_shortages_invoice_id'), 'stock_shortages', ['invoice_id'])
    op.create_index(op.f('ix_stock_shortages_branch_id'), 'stock_shortages', ['branch_id'])


def downgrade() -> None:
    op.drop_table('stock_shortages')
    op.drop_column('invoices', 'stock_consumed_at')
