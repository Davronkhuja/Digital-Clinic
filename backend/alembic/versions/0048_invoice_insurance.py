"""hisob-faktura sug'urta bo'linishi: polis, kafolat xati, sug'urta ulushi

Revision ID: 0048
Revises: 0047
Create Date: 2026-11-30 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0048'
down_revision = '0047'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('invoices', sa.Column('policy_id', sa.UUID(), nullable=True))
    op.add_column('invoices', sa.Column('guarantee_letter_id', sa.UUID(), nullable=True))
    op.add_column('invoices', sa.Column('insurer_id', sa.UUID(), nullable=True))
    op.add_column('invoices', sa.Column('insurer_total', sa.Numeric(14, 2), server_default='0', nullable=False))
    op.create_foreign_key(op.f('fk_invoices_policy_id_patient_policies'), 'invoices', 'patient_policies', ['policy_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key(op.f('fk_invoices_guarantee_letter_id_guarantee_letters'), 'invoices', 'guarantee_letters', ['guarantee_letter_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key(op.f('fk_invoices_insurer_id_insurers'), 'invoices', 'insurers', ['insurer_id'], ['id'], ondelete='RESTRICT')
    op.create_index(op.f('ix_invoices_policy_id'), 'invoices', ['policy_id'])
    op.create_index(op.f('ix_invoices_guarantee_letter_id'), 'invoices', ['guarantee_letter_id'])
    op.create_index(op.f('ix_invoices_insurer_id'), 'invoices', ['insurer_id'])
    op.create_check_constraint(op.f('ck_invoices_insurer_total_range'), 'invoices', 'insurer_total >= 0 AND insurer_total <= total')
    op.add_column('invoice_lines', sa.Column('insurer_amount', sa.Numeric(14, 2), server_default='0', nullable=False))
    op.create_check_constraint(op.f('ck_invoice_lines_insurer_amount_range'), 'invoice_lines', 'insurer_amount >= 0 AND insurer_amount <= net_total')


def downgrade() -> None:
    op.drop_constraint(op.f('ck_invoice_lines_insurer_amount_range'), 'invoice_lines', type_='check')
    op.drop_column('invoice_lines', 'insurer_amount')
    op.drop_constraint(op.f('ck_invoices_insurer_total_range'), 'invoices', type_='check')
    for ix in ('insurer_id', 'guarantee_letter_id', 'policy_id'):
        op.drop_index(op.f(f'ix_invoices_{ix}'), table_name='invoices')
    op.drop_constraint(op.f('fk_invoices_insurer_id_insurers'), 'invoices', type_='foreignkey')
    op.drop_constraint(op.f('fk_invoices_guarantee_letter_id_guarantee_letters'), 'invoices', type_='foreignkey')
    op.drop_constraint(op.f('fk_invoices_policy_id_patient_policies'), 'invoices', type_='foreignkey')
    for col in ('insurer_total', 'insurer_id', 'guarantee_letter_id', 'policy_id'):
        op.drop_column('invoices', col)
