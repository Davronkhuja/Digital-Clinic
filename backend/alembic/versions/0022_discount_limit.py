"""chegirma limiti sozlamasi va finance:discount_override ruxsati

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-16 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('clinic_settings', sa.Column('discount_limit_percent', sa.Numeric(5, 2), server_default='10', nullable=False))
    op.execute("""
        INSERT INTO permissions (code, description) VALUES ('finance:discount_override', 'Limitdan ortiq chegirma berish')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'finance:discount_override' AND r.code = 'admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'finance:discount_override'")
    op.drop_column('clinic_settings', 'discount_limit_percent')
