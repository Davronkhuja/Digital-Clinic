"""ko'rik bo'limlari (shikoyat, anamnez, ko'rik, tavsiya) va ko'rik shablonlari

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-12 11:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ('complaints', 'anamnesis', 'examination', 'recommendations'):
        op.add_column('encounters', sa.Column(col, sa.Text(), nullable=True))
    op.create_table('exam_templates',
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('specialty', sa.String(length=100), nullable=True),
        sa.Column('complaints', sa.Text(), nullable=True),
        sa.Column('anamnesis', sa.Text(), nullable=True),
        sa.Column('examination', sa.Text(), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_exam_templates')),
    )
    op.create_index('uq_exam_templates_name_lower', 'exam_templates', [sa.text('lower(name)')], unique=True)


def downgrade() -> None:
    op.drop_table('exam_templates')
    for col in ('recommendations', 'examination', 'anamnesis', 'complaints'):
        op.drop_column('encounters', col)
