"""Click to'lovini boshqa usulda qaytarish: payment_refunds.refund_method, needs_provider_reconcile

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-16 18:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('payment_refunds', sa.Column(
        'refund_method', sa.Enum('Cash', 'Card', 'Click', 'Payme', name='refund_method', native_enum=False, create_constraint=True, length=6), nullable=True))
    op.add_column('payment_refunds', sa.Column('needs_provider_reconcile', sa.Boolean(), server_default='false', nullable=False))
    # mavjud qaytarishlar: kassa to'lovlari uchun usul = to'lov usuli (Payme avto-qaytarishi null: provayder qaytargan)
    op.execute("""
        UPDATE payment_refunds r SET refund_method = p.method FROM payments p WHERE p.id = r.payment_id AND p.method IN ('Cash', 'Card')
    """)


def downgrade() -> None:
    op.drop_column('payment_refunds', 'needs_provider_reconcile')
    op.drop_column('payment_refunds', 'refund_method')
