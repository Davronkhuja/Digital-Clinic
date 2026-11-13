"""xizmatga bog'langan sarf normalari (tannarx hisobi uchun)

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-21 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('service_materials',
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('qty', sa.Numeric(14, 3), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('qty > 0', name=op.f('ck_service_materials_qty_positive')),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], name=op.f('fk_service_materials_service_id_services'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['item_id'], ['stock_items.id'], name=op.f('fk_service_materials_item_id_stock_items'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_service_materials')),
    )
    op.create_index(op.f('ix_service_materials_service_id'), 'service_materials', ['service_id'])
    op.create_index('uq_service_materials_service_item', 'service_materials', ['service_id', 'item_id'], unique=True)


def downgrade() -> None:
    op.drop_table('service_materials')
