"""laboratoriya natijasini shifokor tasdiqlashi (bemorga ko'rinadi) va lab:approve ruxsati

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-19 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('lab_orders', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('lab_orders', sa.Column('approved_by', sa.UUID(), nullable=True))
    op.execute("""
        INSERT INTO permissions (code, description) VALUES ('lab:approve', 'Laboratoriya natijalarini bemorga ko''rinadigan qilib tasdiqlash (shifokor)')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'lab:approve' AND r.code IN ('admin', 'doctor')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'lab:approve'")
    op.drop_column('lab_orders', 'approved_by')
    op.drop_column('lab_orders', 'approved_at')
