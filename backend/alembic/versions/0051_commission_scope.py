"""shifokor foizi: to'liq summadan (sug'urta ulushi kompaniya to'lagach) yoki faqat bemor to'lovidan

Revision ID: 0051
Revises: 0050
Create Date: 2026-11-16 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0051'
down_revision = '0050'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('clinic_settings', sa.Column('commission_scope', sa.String(length=11), server_default='FullAmount', nullable=False))
    op.alter_column('commission_entries', 'payment_id', existing_type=sa.UUID(), nullable=True)
    op.add_column('commission_entries', sa.Column('insurer_payment_id', sa.UUID(), nullable=True))
    op.add_column('commission_entries', sa.Column('source', sa.String(length=7), server_default='Patient', nullable=False))
    op.create_index(op.f('ix_commission_entries_insurer_payment_id'), 'commission_entries', ['insurer_payment_id'], unique=False)
    op.create_foreign_key(op.f('fk_commission_entries_insurer_payment_id_insurer_payments'), 'commission_entries', 'insurer_payments',
                          ['insurer_payment_id'], ['id'], ondelete='RESTRICT')
    op.create_check_constraint(op.f('ck_commission_entries_source_value'), 'commission_entries', "source IN ('Patient', 'Insurer')")
    op.create_check_constraint(op.f('ck_commission_entries_source_payment'), 'commission_entries',
                               "(source = 'Patient' AND payment_id IS NOT NULL) OR (source = 'Insurer' AND insurer_payment_id IS NOT NULL)")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_commission_entries_source_payment'), 'commission_entries', type_='check')
    op.drop_constraint(op.f('ck_commission_entries_source_value'), 'commission_entries', type_='check')
    op.drop_constraint(op.f('fk_commission_entries_insurer_payment_id_insurer_payments'), 'commission_entries', type_='foreignkey')
    op.drop_index(op.f('ix_commission_entries_insurer_payment_id'), table_name='commission_entries')
    op.drop_column('commission_entries', 'source')
    op.drop_column('commission_entries', 'insurer_payment_id')
    op.alter_column('commission_entries', 'payment_id', existing_type=sa.UUID(), nullable=False)
    op.drop_column('clinic_settings', 'commission_scope')
