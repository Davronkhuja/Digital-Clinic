"""ko'chirishda qisman qabul: qabul qilingan miqdor va tafovutni hal qilish

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-26 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0043'
down_revision = '0042'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('stock_transfer_lines', sa.Column('received_qty', sa.Numeric(14, 3), nullable=True))
    op.add_column('stock_transfer_lines', sa.Column('resolution', sa.String(length=10), nullable=True))
    op.add_column('stock_transfer_lines', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('stock_transfer_lines', sa.Column('resolved_by', sa.UUID(), nullable=True))
    # Avval to'liq qabul qilingan hujjatlar: qabul qilingan miqdor = yuborilgan
    op.execute("""
        UPDATE stock_transfer_lines l SET received_qty = l.qty
        FROM stock_transfers t WHERE l.transfer_id = t.id AND t.status = 'Received'
    """)
    op.create_check_constraint(op.f('ck_stock_transfer_lines_received_range'), 'stock_transfer_lines',
                               'received_qty IS NULL OR (received_qty >= 0 AND received_qty <= qty)')


def downgrade() -> None:
    op.drop_constraint(op.f('ck_stock_transfer_lines_received_range'), 'stock_transfer_lines', type_='check')
    op.drop_column('stock_transfer_lines', 'resolved_by')
    op.drop_column('stock_transfer_lines', 'resolved_at')
    op.drop_column('stock_transfer_lines', 'resolution')
    op.drop_column('stock_transfer_lines', 'received_qty')
