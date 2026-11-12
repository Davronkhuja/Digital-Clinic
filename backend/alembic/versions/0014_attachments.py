"""EMR fayl ilovalari (attachments)

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-13 09:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('attachments',
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('encounter_id', sa.UUID(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=60), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('storage_key', sa.String(length=100), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_attachments_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], name=op.f('fk_attachments_encounter_id_encounters'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_attachments_patient_id_patients'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_attachments')),
        sa.UniqueConstraint('storage_key', name=op.f('uq_attachments_storage_key')),
    )
    op.create_index(op.f('ix_attachments_branch_id'), 'attachments', ['branch_id'])
    op.create_index(op.f('ix_attachments_encounter_id'), 'attachments', ['encounter_id'])
    op.create_index(op.f('ix_attachments_patient_id'), 'attachments', ['patient_id'])


def downgrade() -> None:
    op.drop_table('attachments')
