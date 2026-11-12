"""shifokor foizi: qoidalar, yozuvlar, oylik hisob-kitob; commissions:read/manage ruxsatlari

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-14 16:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def _base() -> list:
    return [
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
    ]


def _enum(name: str, *values: str, length: int) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=length)


def upgrade() -> None:
    op.create_table('commission_rules',
        sa.Column('doctor_id', sa.UUID(), nullable=True),
        sa.Column('service_id', sa.UUID(), nullable=True),
        sa.Column('kind', _enum('kind', 'Percent', 'Fixed', length=8), nullable=False),
        sa.Column('percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('fixed_amount', sa.Numeric(14, 2), nullable=True),
        sa.Column('base', _enum('base', 'WithVat', 'NetOfVat', length=10), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        *_base(),
        sa.CheckConstraint("(kind = 'Percent' AND percent > 0 AND percent <= 100 AND fixed_amount IS NULL) OR "
                           "(kind = 'Fixed' AND fixed_amount > 0 AND percent IS NULL)", name=op.f('ck_commission_rules_kind_value')),
        sa.CheckConstraint('valid_to IS NULL OR valid_to >= valid_from', name=op.f('ck_commission_rules_dates_order')),
        sa.ForeignKeyConstraint(['doctor_id'], ['staff.id'], name=op.f('fk_commission_rules_doctor_id_staff'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], name=op.f('fk_commission_rules_service_id_services'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_commission_rules')),
    )
    op.create_index(op.f('ix_commission_rules_doctor_id'), 'commission_rules', ['doctor_id'])
    op.create_index(op.f('ix_commission_rules_service_id'), 'commission_rules', ['service_id'])

    op.create_table('commission_settlements',
        sa.Column('doctor_id', sa.UUID(), nullable=False),
        sa.Column('month', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('entries_count', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_commission_settlements_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['doctor_id'], ['staff.id'], name=op.f('fk_commission_settlements_doctor_id_staff'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_commission_settlements')),
    )
    op.create_index(op.f('ix_commission_settlements_branch_id'), 'commission_settlements', ['branch_id'])
    op.create_index(op.f('ix_commission_settlements_doctor_id'), 'commission_settlements', ['doctor_id'])

    op.create_table('commission_entries',
        sa.Column('kind', _enum('kind', 'Accrual', 'Reversal', length=9), nullable=False),
        sa.Column('doctor_id', sa.UUID(), nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('payment_id', sa.UUID(), nullable=False),
        sa.Column('refund_id', sa.UUID(), nullable=True),
        sa.Column('invoice_line_id', sa.UUID(), nullable=False),
        sa.Column('accrual_id', sa.UUID(), nullable=True),
        sa.Column('rule_id', sa.UUID(), nullable=True),
        sa.Column('rule_kind', _enum('rule_kind', 'Percent', 'Fixed', length=8), nullable=False),
        sa.Column('rule_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('rule_fixed', sa.Numeric(14, 2), nullable=True),
        sa.Column('base_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('settlement_id', sa.UUID(), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.ForeignKeyConstraint(['accrual_id'], ['commission_entries.id'], name=op.f('fk_commission_entries_accrual_id_commission_entries'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_commission_entries_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['doctor_id'], ['staff.id'], name=op.f('fk_commission_entries_doctor_id_staff'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['invoice_line_id'], ['invoice_lines.id'], name=op.f('fk_commission_entries_invoice_line_id_invoice_lines'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], name=op.f('fk_commission_entries_payment_id_payments'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['refund_id'], ['payment_refunds.id'], name=op.f('fk_commission_entries_refund_id_payment_refunds'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['rule_id'], ['commission_rules.id'], name=op.f('fk_commission_entries_rule_id_commission_rules'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], name=op.f('fk_commission_entries_service_id_services'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['settlement_id'], ['commission_settlements.id'], name=op.f('fk_commission_entries_settlement_id_commission_settlements'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_commission_entries')),
    )
    for col in ('branch_id', 'doctor_id', 'entry_date', 'payment_id'):
        op.create_index(op.f(f'ix_commission_entries_{col}'), 'commission_entries', [col])

    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('commissions:read', 'Shifokor foizi hisobotini ko''rish (o''zingiznikini; boshqarish ruxsati bilan hammasini)'),
          ('commissions:manage', 'Shifokor foizi qoidalari va oylik hisob-kitob')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE (p.code = 'commissions:read' AND r.code IN ('admin', 'doctor'))
           OR (p.code = 'commissions:manage' AND r.code = 'admin')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code IN ('commissions:read', 'commissions:manage')")
    op.drop_table('commission_entries')
    op.drop_table('commission_settlements')
    op.drop_table('commission_rules')
