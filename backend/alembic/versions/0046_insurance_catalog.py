"""sug'urta: kompaniyalar, shartnomalar, qoplanadigan xizmatlar va insurance:* ruxsatlari

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-29 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0046'
down_revision = '0045'
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
    op.create_table('insurers',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('tin', sa.String(length=20), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('address', sa.String(length=300), nullable=True),
        sa.Column('contact_person', sa.String(length=200), nullable=True),
        sa.Column('payment_days', sa.Integer(), server_default='30', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        *_base(),
        sa.CheckConstraint('payment_days >= 0', name=op.f('ck_insurers_payment_days_non_negative')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_insurers')),
    )
    op.create_index('uq_insurers_name_lower', 'insurers', [sa.text('lower(name)')], unique=True)
    op.create_table('insurance_contracts',
        sa.Column('insurer_id', sa.UUID(), nullable=False),
        sa.Column('number', sa.String(length=60), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('discount_percent', sa.Numeric(5, 2), server_default='0', nullable=False),
        sa.Column('coverage_all', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('default_coverage_percent', sa.Numeric(5, 2), server_default='100', nullable=False),
        sa.Column('annual_limit', sa.Numeric(14, 2), nullable=True),
        sa.Column('per_visit_limit', sa.Numeric(14, 2), nullable=True),
        sa.Column('requires_guarantee', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        *_base(),
        sa.CheckConstraint('valid_to IS NULL OR valid_to >= valid_from', name=op.f('ck_insurance_contracts_dates_order')),
        sa.CheckConstraint('discount_percent >= 0 AND discount_percent <= 100', name=op.f('ck_insurance_contracts_discount_range')),
        sa.CheckConstraint('default_coverage_percent > 0 AND default_coverage_percent <= 100', name=op.f('ck_insurance_contracts_coverage_range')),
        sa.CheckConstraint('annual_limit IS NULL OR annual_limit >= 0', name=op.f('ck_insurance_contracts_annual_limit_non_negative')),
        sa.CheckConstraint('per_visit_limit IS NULL OR per_visit_limit >= 0', name=op.f('ck_insurance_contracts_per_visit_limit_non_negative')),
        sa.ForeignKeyConstraint(['insurer_id'], ['insurers.id'], name=op.f('fk_insurance_contracts_insurer_id_insurers'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_insurance_contracts')),
        sa.UniqueConstraint('insurer_id', 'number', name=op.f('uq_insurance_contracts_insurer_id')),
    )
    op.create_index(op.f('ix_insurance_contracts_insurer_id'), 'insurance_contracts', ['insurer_id'])
    op.create_table('insurance_contract_services',
        sa.Column('contract_id', sa.UUID(), nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('coverage_percent', sa.Numeric(5, 2), server_default='100', nullable=False),
        *_base(),
        sa.CheckConstraint('coverage_percent > 0 AND coverage_percent <= 100', name=op.f('ck_insurance_contract_services_coverage_range')),
        sa.ForeignKeyConstraint(['contract_id'], ['insurance_contracts.id'], name=op.f('fk_insurance_contract_services_contract_id_insurance_contracts'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], name=op.f('fk_insurance_contract_services_service_id_services'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_insurance_contract_services')),
        sa.UniqueConstraint('contract_id', 'service_id', name=op.f('uq_insurance_contract_services_contract_id')),
    )
    op.create_index(op.f('ix_insurance_contract_services_contract_id'), 'insurance_contract_services', ['contract_id'])
    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('insurance:read', 'Sug''urta: kompaniyalar, shartnomalar, polislar va kafolat xatlarini ko''rish'),
          ('insurance:write', 'Sug''urta: bemor polisi va kafolat xatini kiritish'),
          ('insurance:manage', 'Sug''urta: kompaniya va shartnomalarni boshqarish, kompaniya to''lovlari, reyestr va qarzdorlik')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE (p.code = 'insurance:read' AND r.code IN ('admin', 'cashier', 'receptionist', 'senior_receptionist'))
           OR (p.code = 'insurance:write' AND r.code IN ('admin', 'receptionist', 'senior_receptionist'))
           OR (p.code = 'insurance:manage' AND r.code = 'admin')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code IN ('insurance:read', 'insurance:write', 'insurance:manage')")
    op.drop_table('insurance_contract_services')
    op.drop_table('insurance_contracts')
    op.drop_table('insurers')
