"""encounters: DMED ga qo'lda ko'chirilgani belgisi

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-12 19:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('encounters', sa.Column('dmed_copied_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('encounters', sa.Column('dmed_copied_by', sa.UUID(), nullable=True))


def downgrade() -> None:
    op.drop_column('encounters', 'dmed_copied_by')
    op.drop_column('encounters', 'dmed_copied_at')
