"""kirim hujjatlari, partiyalar (yaroqlilik muddati) va qoldiq harakatlari jurnali

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-21 11:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None

KINDS = "('Receipt', 'Issue', 'Writeoff', 'TransferOut', 'TransferIn', 'Adjust', 'Consumption')"


def _base() -> list:
    return [
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table('stock_receipts',
        sa.Column('supplier', sa.String(length=200), nullable=True),
        sa.Column('doc_no', sa.String(length=60), nullable=True),
        sa.Column('received_on', sa.Date(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_stock_receipts_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_receipts')),
    )
    op.create_index(op.f('ix_stock_receipts_branch_id'), 'stock_receipts', ['branch_id'])
    op.create_table('stock_batches',
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('receipt_id', sa.UUID(), nullable=True),
        sa.Column('batch_no', sa.String(length=60), nullable=False),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('received_on', sa.Date(), nullable=False),
        sa.Column('unit_cost', sa.Numeric(14, 2), nullable=False),
        sa.Column('qty_received', sa.Numeric(14, 3), nullable=False),
        sa.Column('qty_remaining', sa.Numeric(14, 3), nullable=False),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.CheckConstraint('qty_received > 0', name=op.f('ck_stock_batches_qty_received_positive')),
        sa.CheckConstraint('qty_remaining >= 0 AND qty_remaining <= qty_received', name=op.f('ck_stock_batches_qty_remaining_range')),
        sa.CheckConstraint('unit_cost >= 0', name=op.f('ck_stock_batches_unit_cost_non_negative')),
        sa.ForeignKeyConstraint(['item_id'], ['stock_items.id'], name=op.f('fk_stock_batches_item_id_stock_items'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['receipt_id'], ['stock_receipts.id'], name=op.f('fk_stock_batches_receipt_id_stock_receipts'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_stock_batches_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_batches')),
    )
    op.create_index(op.f('ix_stock_batches_item_id'), 'stock_batches', ['item_id'])
    op.create_index(op.f('ix_stock_batches_branch_id'), 'stock_batches', ['branch_id'])
    op.create_index('ix_stock_batches_fefo', 'stock_batches', ['branch_id', 'item_id', 'expires_on'])
    op.create_table('stock_movements',
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('batch_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('qty', sa.Numeric(14, 3), nullable=False),
        sa.Column('unit_cost', sa.Numeric(14, 2), nullable=False),
        sa.Column('reason', sa.String(length=300), nullable=True),
        sa.Column('ref_type', sa.String(length=30), nullable=True),
        sa.Column('ref_id', sa.UUID(), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.CheckConstraint(f"kind IN {KINDS}", name=op.f('ck_stock_movements_kind')),
        sa.ForeignKeyConstraint(['item_id'], ['stock_items.id'], name=op.f('fk_stock_movements_item_id_stock_items'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['batch_id'], ['stock_batches.id'], name=op.f('fk_stock_movements_batch_id_stock_batches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_stock_movements_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_movements')),
    )
    op.create_index(op.f('ix_stock_movements_batch_id'), 'stock_movements', ['batch_id'])
    op.create_index(op.f('ix_stock_movements_branch_id'), 'stock_movements', ['branch_id'])
    op.create_index('ix_stock_movements_item', 'stock_movements', ['branch_id', 'item_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('stock_movements')
    op.drop_table('stock_batches')
    op.drop_table('stock_receipts')
