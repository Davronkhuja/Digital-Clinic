"""majburan yozish: appointments.override_reason/by, appointments:override ruxsati va katta registrator roli

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-13 15:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('appointments', sa.Column('override_reason', sa.Text(), nullable=True))
    op.add_column('appointments', sa.Column('override_by', sa.UUID(), nullable=True))
    op.execute("""
        INSERT INTO permissions (code, description)
        VALUES ('appointments:override', 'Ish vaqtidan tashqari majburan yozish (sabab bilan; band vaqtga emas)')
        ON CONFLICT (code) DO NOTHING
    """)
    # admin: ruxsat; katta registrator roli faqat mavjud bazada (bo'sh bazada seed yaratadi)
    op.execute("""
        INSERT INTO roles (code, name, is_system)
        SELECT 'senior_receptionist', 'Katta registrator', true
        WHERE EXISTS (SELECT 1 FROM roles WHERE code = 'receptionist')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r JOIN role_permissions rp ON rp.role_id = (SELECT id FROM roles WHERE code = 'receptionist')
        JOIN permissions p ON p.id = rp.permission_id
        WHERE r.code = 'senior_receptionist'
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'appointments:override' AND r.code IN ('admin', 'senior_receptionist')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'appointments:override'")
    op.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE code = 'receptionist') "
               "WHERE role_id = (SELECT id FROM roles WHERE code = 'senior_receptionist')")
    op.execute("DELETE FROM roles WHERE code = 'senior_receptionist'")
    op.drop_column('appointments', 'override_by')
    op.drop_column('appointments', 'override_reason')
