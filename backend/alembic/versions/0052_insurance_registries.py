"""sug'urta reyestri hujjati: Draft -> Sent (qotgan, Excel saqlanadi) -> Reconciled; kompaniya to'lovi reyestrga bog'lanadi

Revision ID: 0052
Revises: 0051
Create Date: 2026-11-16 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0052'
down_revision = '0051'
branch_labels = None
depends_on = None

def base() -> list:
    return [
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table('insurance_registries',
        sa.Column('insurer_id', sa.UUID(), nullable=False),
        sa.Column('month', sa.Date(), nullable=False),
        sa.Column('number', sa.String(length=40), nullable=False),
        sa.Column('status', sa.String(length=10), server_default='Draft', nullable=False),
        sa.Column('insurer_total', sa.Numeric(14, 2), nullable=True),
        sa.Column('patient_total', sa.Numeric(14, 2), nullable=True),
        sa.Column('lines_count', sa.Integer(), nullable=True),
        sa.Column('invoices_count', sa.Integer(), nullable=True),
        sa.Column('file_key', sa.String(length=80), nullable=True),
        sa.Column('file_name', sa.String(length=200), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_sha256', sa.String(length=64), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_by', sa.UUID(), nullable=True),
        sa.Column('reconciled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reconciled_by', sa.UUID(), nullable=True),
        sa.Column('reconcile_note', sa.String(length=500), nullable=True),
        sa.Column('paid_at_reconcile', sa.Numeric(14, 2), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *base(),
        sa.CheckConstraint("status IN ('Draft', 'Sent', 'Reconciled')", name=op.f('ck_insurance_registries_status_value')),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_insurance_registries_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['insurer_id'], ['insurers.id'], name=op.f('fk_insurance_registries_insurer_id_insurers'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_insurance_registries')),
        sa.UniqueConstraint('insurer_id', 'month', 'branch_id', name=op.f('uq_insurance_registries_insurer_id')),
        sa.UniqueConstraint('number', name=op.f('uq_insurance_registries_number')),
    )
    op.create_index(op.f('ix_insurance_registries_insurer_id'), 'insurance_registries', ['insurer_id'], unique=False)
    op.create_index(op.f('ix_insurance_registries_branch_id'), 'insurance_registries', ['branch_id'], unique=False)
    op.create_table('insurance_registry_lines',
        sa.Column('registry_id', sa.UUID(), nullable=False),
        sa.Column('invoice_line_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('line_date', sa.Date(), nullable=False),
        sa.Column('invoice_number', sa.String(length=30), nullable=False),
        sa.Column('patient', sa.String(length=200), nullable=False),
        sa.Column('policy', sa.String(length=50), nullable=True),
        sa.Column('letter', sa.String(length=50), nullable=True),
        sa.Column('contract', sa.String(length=50), nullable=True),
        sa.Column('service', sa.String(length=300), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False),
        sa.Column('line_total', sa.Numeric(14, 2), nullable=False),
        sa.Column('insurer_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('patient_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('branch', sa.String(length=200), nullable=False),
        *base(),
        sa.CheckConstraint("kind IN ('Original', 'Correction')", name=op.f('ck_insurance_registry_lines_kind_value')),
        sa.ForeignKeyConstraint(['registry_id'], ['insurance_registries.id'], name=op.f('fk_insurance_registry_lines_registry_id_insurance_registries'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['invoice_line_id'], ['invoice_lines.id'], name=op.f('fk_insurance_registry_lines_invoice_line_id_invoice_lines'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_insurance_registry_lines')),
    )
    op.create_index(op.f('ix_insurance_registry_lines_registry_id'), 'insurance_registry_lines', ['registry_id'], unique=False)
    op.create_index(op.f('ix_insurance_registry_lines_invoice_line_id'), 'insurance_registry_lines', ['invoice_line_id'], unique=False)
    op.add_column('insurer_payments', sa.Column('registry_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_insurer_payments_registry_id'), 'insurer_payments', ['registry_id'], unique=False)
    op.create_foreign_key(op.f('fk_insurer_payments_registry_id_insurance_registries'), 'insurer_payments', 'insurance_registries', ['registry_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> None:
    op.drop_constraint(op.f('fk_insurer_payments_registry_id_insurance_registries'), 'insurer_payments', type_='foreignkey')
    op.drop_index(op.f('ix_insurer_payments_registry_id'), table_name='insurer_payments')
    op.drop_column('insurer_payments', 'registry_id')
    op.drop_table('insurance_registry_lines')
    op.drop_table('insurance_registries')
