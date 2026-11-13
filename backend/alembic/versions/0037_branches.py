"""filiallar: is_active, nom noyob, branches:manage va branches:all ruxsatlari

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-22 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('branches', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
    op.create_index('uq_branches_name_lower', 'branches', [sa.text('lower(name)')], unique=True)
    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('branches:manage', 'Filiallarni qo''shish, o''zgartirish va foydalanuvchini filialga biriktirish'),
          ('branches:all', 'Boshqa filialga o''tib ishlash (faol filialni almashtirish)')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code IN ('branches:manage', 'branches:all') AND r.code = 'admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code IN ('branches:manage', 'branches:all')")
    op.drop_index('uq_branches_name_lower', table_name='branches')
    op.drop_column('branches', 'is_active')
