"""sarf xizmat bajarilganda: invoice_lines.performed_at, stock_shortages.invoice_line_id, harakat turi Return

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-23 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None

OLD = "('Receipt', 'Issue', 'Writeoff', 'TransferOut', 'TransferIn', 'Adjust', 'Consumption')"
NEW = "('Receipt', 'Issue', 'Writeoff', 'TransferOut', 'TransferIn', 'Adjust', 'Consumption', 'Return')"


def upgrade() -> None:
    op.add_column('invoice_lines', sa.Column('performed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('invoice_lines', sa.Column('performed_by', sa.UUID(), nullable=True))
    # Avval to'lovda yozilgan sarf: o'sha hisob-faktura qatorlari bajarilgan hisoblanadi (qayta yozilmasin)
    op.execute("""
        UPDATE invoice_lines l SET performed_at = i.stock_consumed_at
        FROM invoices i WHERE l.invoice_id = i.id AND i.stock_consumed_at IS NOT NULL
    """)
    op.drop_column('invoices', 'stock_consumed_at')
    op.add_column('stock_shortages', sa.Column('invoice_line_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_stock_shortages_invoice_line_id_invoice_lines'), 'stock_shortages', 'invoice_lines', ['invoice_line_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint(op.f('ck_stock_movements_kind'), 'stock_movements', type_='check')
    op.create_check_constraint(op.f('ck_stock_movements_kind'), 'stock_movements', f"kind IN {NEW}")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_stock_movements_kind'), 'stock_movements', type_='check')
    op.execute("DELETE FROM stock_movements WHERE kind = 'Return'")
    op.create_check_constraint(op.f('ck_stock_movements_kind'), 'stock_movements', f"kind IN {OLD}")
    op.drop_constraint(op.f('fk_stock_shortages_invoice_line_id_invoice_lines'), 'stock_shortages', type_='foreignkey')
    op.drop_column('stock_shortages', 'invoice_line_id')
    op.add_column('invoices', sa.Column('stock_consumed_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_column('invoice_lines', 'performed_by')
    op.drop_column('invoice_lines', 'performed_at')
