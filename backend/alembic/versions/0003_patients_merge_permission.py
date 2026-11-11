"""patients:merge ruxsati (admin va receptionist) va birlashtirish endi patients:delete talab qilmaydi

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11 11:00:00
"""
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO permissions (code, description)
        VALUES ('patients:merge', 'Bemor dublikatlarini birlashtirish')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE r.code IN ('admin', 'receptionist') AND p.code = 'patients:merge'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'patients:merge'")  # role_permissions CASCADE
