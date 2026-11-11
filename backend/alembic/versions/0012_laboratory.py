"""laboratoriya: katalog, me'yorlar, to'plamlar, buyurtmalar, natijalar; lab:read/lab:write ruxsatlari

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-12 17:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
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
    op.create_table('lab_tests',
        sa.Column('code', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('unit', sa.String(length=30), nullable=True),
        sa.Column('category', sa.String(length=60), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        *_base(),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_tests')),
    )
    op.create_index('uq_lab_tests_code_lower', 'lab_tests', [sa.text('lower(code)')], unique=True)

    op.create_table('lab_reference_ranges',
        sa.Column('test_id', sa.UUID(), nullable=False),
        sa.Column('sex', sa.Enum('male', 'female', 'other', name='range_sex', native_enum=False, create_constraint=True, length=10), nullable=True),
        sa.Column('age_min', sa.Integer(), nullable=True),
        sa.Column('age_max', sa.Integer(), nullable=True),
        sa.Column('low', sa.Numeric(14, 4), nullable=True),
        sa.Column('high', sa.Numeric(14, 4), nullable=True),
        sa.Column('note', sa.String(length=200), nullable=True),
        *_base(),
        sa.CheckConstraint('low IS NOT NULL OR high IS NOT NULL', name=op.f('ck_lab_reference_ranges_has_bound')),
        sa.CheckConstraint('low IS NULL OR high IS NULL OR low <= high', name=op.f('ck_lab_reference_ranges_low_le_high')),
        sa.CheckConstraint('age_min IS NULL OR age_max IS NULL OR age_min <= age_max', name=op.f('ck_lab_reference_ranges_age_order')),
        sa.ForeignKeyConstraint(['test_id'], ['lab_tests.id'], name=op.f('fk_lab_reference_ranges_test_id_lab_tests'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_reference_ranges')),
    )
    op.create_index(op.f('ix_lab_reference_ranges_test_id'), 'lab_reference_ranges', ['test_id'])

    op.create_table('lab_panels',
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        *_base(),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_panels')),
    )
    op.create_index('uq_lab_panels_name_lower', 'lab_panels', [sa.text('lower(name)')], unique=True)

    op.create_table('lab_panel_tests',
        sa.Column('panel_id', sa.UUID(), nullable=False),
        sa.Column('test_id', sa.UUID(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        *_base(),
        sa.ForeignKeyConstraint(['panel_id'], ['lab_panels.id'], name=op.f('fk_lab_panel_tests_panel_id_lab_panels'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_id'], ['lab_tests.id'], name=op.f('fk_lab_panel_tests_test_id_lab_tests'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_panel_tests')),
        sa.UniqueConstraint('panel_id', 'test_id', name=op.f('uq_lab_panel_tests_panel_id')),
    )
    op.create_index(op.f('ix_lab_panel_tests_panel_id'), 'lab_panel_tests', ['panel_id'])

    op.create_table('lab_orders',
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('doctor_id', sa.UUID(), nullable=False),
        sa.Column('encounter_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.Enum('Ordered', 'Completed', 'Cancelled', name='status', native_enum=False, create_constraint=True, length=10), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_lab_orders_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['doctor_id'], ['staff.id'], name=op.f('fk_lab_orders_doctor_id_staff'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], name=op.f('fk_lab_orders_encounter_id_encounters'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_lab_orders_patient_id_patients'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_orders')),
    )
    op.create_index(op.f('ix_lab_orders_branch_id'), 'lab_orders', ['branch_id'])
    op.create_index(op.f('ix_lab_orders_patient_id'), 'lab_orders', ['patient_id'])

    op.create_table('lab_order_items',
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('test_id', sa.UUID(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('test_name', sa.String(length=150), nullable=False),
        sa.Column('unit', sa.String(length=30), nullable=True),
        sa.Column('value', sa.Numeric(14, 4), nullable=True),
        sa.Column('flag', sa.Enum('Low', 'Normal', 'High', name='flag', native_enum=False, create_constraint=True, length=8), nullable=True),
        sa.Column('ref_low', sa.Numeric(14, 4), nullable=True),
        sa.Column('ref_high', sa.Numeric(14, 4), nullable=True),
        sa.Column('resulted_at', sa.DateTime(timezone=True), nullable=True),
        *_base(),
        sa.ForeignKeyConstraint(['order_id'], ['lab_orders.id'], name=op.f('fk_lab_order_items_order_id_lab_orders'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['test_id'], ['lab_tests.id'], name=op.f('fk_lab_order_items_test_id_lab_tests'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_order_items')),
        sa.UniqueConstraint('order_id', 'test_id', name=op.f('uq_lab_order_items_order_id')),
    )
    op.create_index(op.f('ix_lab_order_items_order_id'), 'lab_order_items', ['order_id'])

    # ruxsatlar: admin, shifokor, hamshira
    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('lab:read', 'Laboratoriya buyurtma va natijalarini ko''rish'),
          ('lab:write', 'Laboratoriya buyurtma berish va natija kiritish')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code IN ('lab:read', 'lab:write') AND r.code IN ('admin', 'doctor', 'nurse')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code IN ('lab:read', 'lab:write')")
    op.drop_table('lab_order_items')
    op.drop_table('lab_orders')
    op.drop_table('lab_panel_tests')
    op.drop_table('lab_panels')
    op.drop_table('lab_reference_ranges')
    op.drop_table('lab_tests')
