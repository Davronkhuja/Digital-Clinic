"""filiallar orasida ombor ko'chirish hujjatlari va warehouse:transfer ruxsati

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-22 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None


def _base() -> list:
    return [
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
    ]


def upgrade() -> None:
    op.execute(sa.schema.CreateSequence(sa.Sequence('stock_transfer_number_seq')))
    op.create_table('stock_transfers',
        sa.Column('number', sa.String(length=20), nullable=False),
        sa.Column('from_branch_id', sa.UUID(), nullable=False),
        sa.Column('to_branch_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('received_by', sa.UUID(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_reason', sa.String(length=300), nullable=True),
        *_base(),
        sa.CheckConstraint('from_branch_id <> to_branch_id', name=op.f('ck_stock_transfers_different_branches')),
        sa.CheckConstraint("status IN ('Sent', 'Received', 'Cancelled')", name=op.f('ck_stock_transfers_status')),
        sa.ForeignKeyConstraint(['from_branch_id'], ['branches.id'], name=op.f('fk_stock_transfers_from_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['to_branch_id'], ['branches.id'], name=op.f('fk_stock_transfers_to_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_transfers')),
        sa.UniqueConstraint('number', name=op.f('uq_stock_transfers_number')),
    )
    op.create_index(op.f('ix_stock_transfers_from_branch_id'), 'stock_transfers', ['from_branch_id'])
    op.create_index(op.f('ix_stock_transfers_to_branch_id'), 'stock_transfers', ['to_branch_id'])
    op.create_table('stock_transfer_lines',
        sa.Column('transfer_id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('source_batch_id', sa.UUID(), nullable=False),
        sa.Column('dest_batch_id', sa.UUID(), nullable=True),
        sa.Column('batch_no', sa.String(length=60), nullable=False),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('unit_cost', sa.Numeric(14, 2), nullable=False),
        sa.Column('qty', sa.Numeric(14, 3), nullable=False),
        *_base(),
        sa.CheckConstraint('qty > 0', name=op.f('ck_stock_transfer_lines_qty_positive')),
        sa.ForeignKeyConstraint(['transfer_id'], ['stock_transfers.id'], name=op.f('fk_stock_transfer_lines_transfer_id_stock_transfers'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['item_id'], ['stock_items.id'], name=op.f('fk_stock_transfer_lines_item_id_stock_items'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_batch_id'], ['stock_batches.id'], name=op.f('fk_stock_transfer_lines_source_batch_id_stock_batches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['dest_batch_id'], ['stock_batches.id'], name=op.f('fk_stock_transfer_lines_dest_batch_id_stock_batches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_transfer_lines')),
    )
    op.create_index(op.f('ix_stock_transfer_lines_transfer_id'), 'stock_transfer_lines', ['transfer_id'])
    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('warehouse:transfer', 'Ombor: filiallar orasida ko''chirish hujjatini yuborish, qabul qilish va bekor qilish')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'warehouse:transfer' AND r.code IN ('admin', 'nurse')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'warehouse:transfer'")
    op.drop_table('stock_transfer_lines')
    op.drop_table('stock_transfers')
    op.execute(sa.schema.DropSequence(sa.Sequence('stock_transfer_number_seq')))
