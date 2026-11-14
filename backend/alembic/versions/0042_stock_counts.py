"""inventarizatsiya (sanoq) hujjatlari va warehouse:approve ruxsati

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-25 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0042'
down_revision = '0041'
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
    op.execute(sa.schema.CreateSequence(sa.Sequence('stock_count_number_seq')))
    op.create_table('stock_counts',
        sa.Column('number', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_by', sa.UUID(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_reason', sa.String(length=300), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.CheckConstraint("status IN ('Draft', 'Submitted', 'Approved', 'Cancelled')", name=op.f('ck_stock_counts_status')),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_stock_counts_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_counts')),
        sa.UniqueConstraint('number', name=op.f('uq_stock_counts_number')),
    )
    op.create_index(op.f('ix_stock_counts_branch_id'), 'stock_counts', ['branch_id'])
    op.create_table('stock_count_lines',
        sa.Column('count_id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('batch_id', sa.UUID(), nullable=True),
        sa.Column('batch_no', sa.String(length=60), nullable=False),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('unit_cost', sa.Numeric(14, 2), nullable=False),
        sa.Column('expected_qty', sa.Numeric(14, 3), nullable=False),
        sa.Column('counted_qty', sa.Numeric(14, 3), nullable=True),
        *_base(),
        sa.CheckConstraint('counted_qty IS NULL OR counted_qty >= 0', name=op.f('ck_stock_count_lines_counted_non_negative')),
        sa.ForeignKeyConstraint(['count_id'], ['stock_counts.id'], name=op.f('fk_stock_count_lines_count_id_stock_counts'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['item_id'], ['stock_items.id'], name=op.f('fk_stock_count_lines_item_id_stock_items'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['batch_id'], ['stock_batches.id'], name=op.f('fk_stock_count_lines_batch_id_stock_batches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_count_lines')),
    )
    op.create_index(op.f('ix_stock_count_lines_count_id'), 'stock_count_lines', ['count_id'])
    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('warehouse:approve', 'Ombor: inventarizatsiya farqini tasdiqlash (avtomatik kirim/chiqim yoziladi)')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'warehouse:approve' AND r.code = 'admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'warehouse:approve'")
    op.drop_table('stock_count_lines')
    op.drop_table('stock_counts')
    op.execute(sa.schema.DropSequence(sa.Sequence('stock_count_number_seq')))
