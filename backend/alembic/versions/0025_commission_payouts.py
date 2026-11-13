"""shifokor foizi to'lov hujjatlari (draft -> approved -> paid), commissions:pay ruxsati

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-16 16:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('commission_payouts',
        sa.Column('settlement_id', sa.UUID(), nullable=False),
        sa.Column('doctor_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('status', sa.Enum('Draft', 'Approved', 'Paid', name='status', native_enum=False, create_constraint=True, length=8), nullable=False),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_by', sa.UUID(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pay_method', sa.Enum('Cash', 'Transfer', name='pay_method', native_enum=False, create_constraint=True, length=8), nullable=True),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('amount > 0', name=op.f('ck_commission_payouts_amount_positive')),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_commission_payouts_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['doctor_id'], ['staff.id'], name=op.f('fk_commission_payouts_doctor_id_staff'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['settlement_id'], ['commission_settlements.id'], name=op.f('fk_commission_payouts_settlement_id_commission_settlements'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_commission_payouts')),
        sa.UniqueConstraint('settlement_id', name=op.f('uq_commission_payouts_settlement_id')),
    )
    op.create_index(op.f('ix_commission_payouts_branch_id'), 'commission_payouts', ['branch_id'])
    op.create_index(op.f('ix_commission_payouts_doctor_id'), 'commission_payouts', ['doctor_id'])
    op.add_column('transactions', sa.Column('payout_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_transactions_payout_id_commission_payouts'), 'transactions', 'commission_payouts', ['payout_id'], ['id'], ondelete='RESTRICT')
    op.create_unique_constraint(op.f('uq_transactions_payout_id'), 'transactions', ['payout_id'])
    op.create_foreign_key(op.f('fk_cash_movements_payout_id_commission_payouts'), 'cash_movements', 'commission_payouts', ['payout_id'], ['id'], ondelete='RESTRICT')
    op.create_unique_constraint(op.f('uq_cash_movements_payout_id'), 'cash_movements', ['payout_id'])
    op.execute("""
        INSERT INTO permissions (code, description) VALUES ('commissions:pay', 'Shifokor foizi to''lovini bajarish (naqd/o''tkazma)')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'commissions:pay' AND r.code = 'admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'commissions:pay'")
    op.drop_constraint(op.f('uq_cash_movements_payout_id'), 'cash_movements', type_='unique')
    op.drop_constraint(op.f('fk_cash_movements_payout_id_commission_payouts'), 'cash_movements', type_='foreignkey')
    op.drop_constraint(op.f('uq_transactions_payout_id'), 'transactions', type_='unique')
    op.drop_constraint(op.f('fk_transactions_payout_id_commission_payouts'), 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'payout_id')
    op.drop_table('commission_payouts')
