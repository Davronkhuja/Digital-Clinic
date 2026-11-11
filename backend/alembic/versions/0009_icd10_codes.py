"""MKB-10 ma'lumotnomasi (icd10_codes)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-12 09:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('icd10_codes',
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('name_uz', sa.String(length=300), nullable=False),
        sa.Column('name_en', sa.String(length=300), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_icd10_codes')),
        sa.UniqueConstraint('code', name=op.f('uq_icd10_codes_code')),
    )


def downgrade() -> None:
    op.drop_table('icd10_codes')
