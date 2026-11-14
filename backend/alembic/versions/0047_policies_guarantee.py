"""sug'urta: bemor polislari va kafolat xatlari (fayl ilovasi bilan)

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-29 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0047'
down_revision = '0046'
branch_labels = None
depends_on = None


def _base() -> list:
    return [
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table('patient_policies',
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('insurer_id', sa.UUID(), nullable=False),
        sa.Column('contract_id', sa.UUID(), nullable=False),
        sa.Column('number', sa.String(length=60), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        *_base(),
        sa.CheckConstraint('valid_to IS NULL OR valid_to >= valid_from', name=op.f('ck_patient_policies_dates_order')),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_patient_policies_patient_id_patients'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['insurer_id'], ['insurers.id'], name=op.f('fk_patient_policies_insurer_id_insurers'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['contract_id'], ['insurance_contracts.id'], name=op.f('fk_patient_policies_contract_id_insurance_contracts'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_patient_policies')),
        sa.UniqueConstraint('insurer_id', 'number', name=op.f('uq_patient_policies_insurer_id')),
    )
    op.create_index(op.f('ix_patient_policies_patient_id'), 'patient_policies', ['patient_id'])
    op.create_index(op.f('ix_patient_policies_insurer_id'), 'patient_policies', ['insurer_id'])
    op.create_index(op.f('ix_patient_policies_contract_id'), 'patient_policies', ['contract_id'])
    op.create_table('guarantee_letters',
        sa.Column('insurer_id', sa.UUID(), nullable=False),
        sa.Column('policy_id', sa.UUID(), nullable=False),
        sa.Column('number', sa.String(length=60), nullable=False),
        sa.Column('letter_date', sa.Date(), nullable=False),
        sa.Column('amount_limit', sa.Numeric(14, 2), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=True),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=10), server_default='Active', nullable=False),
        sa.Column('cancel_reason', sa.String(length=300), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('file_key', sa.String(length=80), nullable=True),
        sa.Column('file_name', sa.String(length=200), nullable=True),
        sa.Column('file_type', sa.String(length=60), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        *_base(),
        sa.CheckConstraint('amount_limit > 0', name=op.f('ck_guarantee_letters_amount_limit_positive')),
        sa.CheckConstraint('valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from', name=op.f('ck_guarantee_letters_dates_order')),
        sa.CheckConstraint("status IN ('Active', 'Cancelled')", name=op.f('ck_guarantee_letters_status_values')),
        sa.ForeignKeyConstraint(['insurer_id'], ['insurers.id'], name=op.f('fk_guarantee_letters_insurer_id_insurers'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['policy_id'], ['patient_policies.id'], name=op.f('fk_guarantee_letters_policy_id_patient_policies'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_guarantee_letters')),
        sa.UniqueConstraint('insurer_id', 'number', name=op.f('uq_guarantee_letters_insurer_id')),
    )
    op.create_index(op.f('ix_guarantee_letters_insurer_id'), 'guarantee_letters', ['insurer_id'])
    op.create_index(op.f('ix_guarantee_letters_policy_id'), 'guarantee_letters', ['policy_id'])
    op.create_table('guarantee_letter_services',
        sa.Column('letter_id', sa.UUID(), nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        *_base(),
        sa.ForeignKeyConstraint(['letter_id'], ['guarantee_letters.id'], name=op.f('fk_guarantee_letter_services_letter_id_guarantee_letters'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], name=op.f('fk_guarantee_letter_services_service_id_services'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_guarantee_letter_services')),
        sa.UniqueConstraint('letter_id', 'service_id', name=op.f('uq_guarantee_letter_services_letter_id')),
    )
    op.create_index(op.f('ix_guarantee_letter_services_letter_id'), 'guarantee_letter_services', ['letter_id'])


def downgrade() -> None:
    op.drop_table('guarantee_letter_services')
    op.drop_table('guarantee_letters')
    op.drop_table('patient_policies')
