"""ombor katalogi (dori va sarf materiallari) va warehouse:read/write ruxsatlari

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-21 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0033'
down_revision = '0032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('stock_items',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('sku', sa.String(length=50), nullable=True),
        sa.Column('min_qty', sa.Numeric(14, 3), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('min_qty >= 0', name=op.f('ck_stock_items_min_qty_non_negative')),
        sa.CheckConstraint("kind IN ('Medicine', 'Supply')", name=op.f('ck_stock_items_kind')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_items')),
    )
    op.create_index('uq_stock_items_name_lower', 'stock_items', [sa.text('lower(name)')], unique=True)
    op.create_index('uq_stock_items_sku_lower', 'stock_items', [sa.text('lower(sku)')], unique=True, postgresql_where=sa.text('sku IS NOT NULL'))
    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('warehouse:read', 'Ombor: katalog, qoldiq va ogohlantirishlarni ko''rish'),
          ('warehouse:write', 'Ombor: katalog, kirim, chiqim va hisobdan chiqarish')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE (p.code = 'warehouse:read' AND r.code IN ('admin', 'doctor', 'nurse'))
           OR (p.code = 'warehouse:write' AND r.code IN ('admin', 'nurse'))
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code IN ('warehouse:read', 'warehouse:write')")
    op.drop_table('stock_items')
