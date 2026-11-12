"""narxnoma: xizmat kategoriyalari va xizmatlar (MXIK, package_code, QQS); services:read/write ruxsatlari

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-13 18:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0017'
down_revision = '0016'
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
    op.create_table('service_categories',
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        *_base(),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_service_categories')),
    )
    op.create_index('uq_service_categories_name_lower', 'service_categories', [sa.text('lower(name)')], unique=True)
    op.create_table('services',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('price', sa.Numeric(14, 2), nullable=False),
        sa.Column('mxik', sa.String(length=17), nullable=True),
        sa.Column('package_code', sa.String(length=10), nullable=True),
        sa.Column('vat_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        *_base(),
        sa.CheckConstraint('price >= 0', name=op.f('ck_services_price_non_negative')),
        sa.CheckConstraint("mxik IS NULL OR mxik ~ '^[0-9]{17}$'", name=op.f('ck_services_mxik_format')),
        sa.CheckConstraint("package_code IS NULL OR package_code ~ '^[0-9]{1,10}$'", name=op.f('ck_services_package_code_format')),
        sa.CheckConstraint('vat_percent IS NULL OR (vat_percent >= 0 AND vat_percent <= 100)', name=op.f('ck_services_vat_range')),
        sa.ForeignKeyConstraint(['category_id'], ['service_categories.id'], name=op.f('fk_services_category_id_service_categories'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_services')),
    )
    op.create_index('uq_services_name_lower', 'services', [sa.text('lower(name)')], unique=True)

    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('services:read', 'Narxnomani (xizmatlar) ko''rish'),
          ('services:write', 'Narxnomani o''zgartirish (narx, MXIK, QQS)')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE (p.code = 'services:read' AND r.code IN ('admin', 'doctor', 'receptionist', 'senior_receptionist', 'cashier'))
           OR (p.code = 'services:write' AND r.code = 'admin')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code IN ('services:read', 'services:write')")
    op.drop_table('services')
    op.drop_table('service_categories')
