"""tasdiqlangan lab natijasiga tuzatish yozuvlari

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-20 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None

FLAGS = "('Low', 'Normal', 'High')"


def upgrade() -> None:
    op.create_table('lab_corrections',
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('old_value', sa.Numeric(14, 4), nullable=True),
        sa.Column('new_value', sa.Numeric(14, 4), nullable=False),
        sa.Column('old_flag', sa.String(length=8), nullable=True),
        sa.Column('new_flag', sa.String(length=8), nullable=True),
        sa.Column('corrected_by_name', sa.String(length=150), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint(f"old_flag IS NULL OR old_flag IN {FLAGS}", name=op.f('ck_lab_corrections_old_flag')),
        sa.CheckConstraint(f"new_flag IS NULL OR new_flag IN {FLAGS}", name=op.f('ck_lab_corrections_new_flag')),
        sa.ForeignKeyConstraint(['order_id'], ['lab_orders.id'], name=op.f('fk_lab_corrections_order_id_lab_orders'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['item_id'], ['lab_order_items.id'], name=op.f('fk_lab_corrections_item_id_lab_order_items'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_corrections')),
    )
    op.create_index(op.f('ix_lab_corrections_order_id'), 'lab_corrections', ['order_id'])


def downgrade() -> None:
    op.drop_table('lab_corrections')
