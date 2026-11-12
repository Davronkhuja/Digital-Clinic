"""to'lovlar, qaytarishlar, fiskal chek maydonlari, transactions.payment_id/refund_id, finance:refund ruxsati

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-14 10:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def _base() -> list:
    return [
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
    ]


def _receipt_status(name: str = 'receipt_status') -> sa.Enum:
    return sa.Enum('Pending', 'Issued', 'Failed', name=name, native_enum=False, create_constraint=True, length=8)


def upgrade() -> None:
    op.create_table('payments',
        sa.Column('invoice_id', sa.UUID(), nullable=False),
        sa.Column('method', sa.Enum('Cash', 'Card', 'Click', 'Payme', name='method', native_enum=False, create_constraint=True, length=6), nullable=False),
        sa.Column('status', sa.Enum('Pending', 'Paid', 'Failed', 'Cancelled', name='status', native_enum=False, create_constraint=True, length=10), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('provider_txn_id', sa.String(length=100), nullable=True),
        sa.Column('provider_state', sa.Integer(), nullable=True),
        sa.Column('provider_data', postgresql.JSONB(), nullable=True),
        sa.Column('receipt_status', _receipt_status(), nullable=True),
        sa.Column('receipt_id', sa.String(length=100), nullable=True),
        sa.Column('receipt_data', postgresql.JSONB(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.CheckConstraint('amount > 0', name=op.f('ck_payments_amount_positive')),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_payments_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_payments_invoice_id_invoices'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
    )
    op.create_index(op.f('ix_payments_branch_id'), 'payments', ['branch_id'])
    op.create_index(op.f('ix_payments_invoice_id'), 'payments', ['invoice_id'])
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'])
    op.create_index('uq_payments_provider_txn', 'payments', ['method', 'provider_txn_id'], unique=True,
                    postgresql_where=sa.text('provider_txn_id IS NOT NULL'))

    op.create_table('payment_refunds',
        sa.Column('payment_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('provider_reason', sa.Integer(), nullable=True),
        sa.Column('receipt_status', _receipt_status(), nullable=True),
        sa.Column('receipt_id', sa.String(length=100), nullable=True),
        sa.Column('receipt_data', postgresql.JSONB(), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.CheckConstraint('amount > 0', name=op.f('ck_payment_refunds_amount_positive')),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_payment_refunds_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], name=op.f('fk_payment_refunds_payment_id_payments'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_refunds')),
    )
    op.create_index(op.f('ix_payment_refunds_branch_id'), 'payment_refunds', ['branch_id'])
    op.create_index(op.f('ix_payment_refunds_payment_id'), 'payment_refunds', ['payment_id'])

    op.add_column('transactions', sa.Column('payment_id', sa.UUID(), nullable=True))
    op.add_column('transactions', sa.Column('refund_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_transactions_payment_id_payments'), 'transactions', 'payments', ['payment_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key(op.f('fk_transactions_refund_id_payment_refunds'), 'transactions', 'payment_refunds', ['refund_id'], ['id'], ondelete='RESTRICT')
    op.create_unique_constraint(op.f('uq_transactions_payment_id'), 'transactions', ['payment_id'])
    op.create_unique_constraint(op.f('uq_transactions_refund_id'), 'transactions', ['refund_id'])

    op.execute("""
        INSERT INTO permissions (code, description) VALUES ('finance:refund', 'To''lovni qaytarish')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'finance:refund' AND r.code = 'admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'finance:refund'")
    op.drop_constraint(op.f('uq_transactions_refund_id'), 'transactions', type_='unique')
    op.drop_constraint(op.f('uq_transactions_payment_id'), 'transactions', type_='unique')
    op.drop_constraint(op.f('fk_transactions_refund_id_payment_refunds'), 'transactions', type_='foreignkey')
    op.drop_constraint(op.f('fk_transactions_payment_id_payments'), 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'refund_id')
    op.drop_column('transactions', 'payment_id')
    op.drop_table('payment_refunds')
    op.drop_table('payments')
