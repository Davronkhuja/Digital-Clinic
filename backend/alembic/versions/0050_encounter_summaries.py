"""ko'rikning AI xulosasi: qoralama va shifokor tasdig'i

Revision ID: 0050
Revises: 0049
Create Date: 2026-12-02 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0050'
down_revision = '0049'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('encounter_summaries',
        sa.Column('encounter_id', sa.UUID(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=10), server_default='Draft', nullable=False),
        sa.Column('source', sa.String(length=5), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('generated_by', sa.UUID(), nullable=True),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('edited', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint("status IN ('Draft', 'Approved', 'Rejected', 'Superseded')", name=op.f('ck_encounter_summaries_status_values')),
        sa.CheckConstraint("source IN ('llm', 'demo')", name=op.f('ck_encounter_summaries_source_values')),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], name=op.f('fk_encounter_summaries_encounter_id_encounters'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_encounter_summaries_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_encounter_summaries')),
    )
    op.create_index(op.f('ix_encounter_summaries_branch_id'), 'encounter_summaries', ['branch_id'])
    op.create_index('ix_encounter_summaries_encounter', 'encounter_summaries', ['encounter_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('encounter_summaries')
