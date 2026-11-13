"""kassa naqd chiqimlari (inkassatsiya, foiz to'lovi) va finance:cash_withdrawal ruxsati

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-16 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('cash_movements',
        sa.Column('shift_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.Enum('Withdrawal', 'Payout', name='kind', native_enum=False, create_constraint=True, length=10), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('counterparty', sa.String(length=200), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('payout_id', sa.UUID(), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('amount > 0', name=op.f('ck_cash_movements_amount_positive')),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_cash_movements_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['shift_id'], ['cash_shifts.id'], name=op.f('fk_cash_movements_shift_id_cash_shifts'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_cash_movements')),
    )
    op.create_index(op.f('ix_cash_movements_branch_id'), 'cash_movements', ['branch_id'])
    op.create_index(op.f('ix_cash_movements_shift_id'), 'cash_movements', ['shift_id'])
    op.execute("""
        INSERT INTO permissions (code, description) VALUES ('finance:cash_withdrawal', 'Kassadan inkassatsiya (naqd chiqarish)')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'finance:cash_withdrawal' AND r.code = 'admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'finance:cash_withdrawal'")
    op.drop_table('cash_movements')
