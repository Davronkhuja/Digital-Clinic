"""qabulni tasdiqlash/bekor qilish izi: confirmed_at, cancelled_at, cancel_source

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-17 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('appointments', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('cancel_source', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('appointments', 'cancel_source')
    op.drop_column('appointments', 'cancelled_at')
    op.drop_column('appointments', 'confirmed_at')
