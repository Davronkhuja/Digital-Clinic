"""sug'urta kompaniyalaridan kelgan to'lovlar

Revision ID: 0049
Revises: 0048
Create Date: 2026-12-01 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0049'
down_revision = '0048'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('insurer_payments',
        sa.Column('insurer_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('paid_on', sa.Date(), nullable=False),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reverse_reason', sa.String(length=300), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('amount > 0', name=op.f('ck_insurer_payments_amount_positive')),
        sa.ForeignKeyConstraint(['insurer_id'], ['insurers.id'], name=op.f('fk_insurer_payments_insurer_id_insurers'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_insurer_payments_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_insurer_payments')),
    )
    op.create_index(op.f('ix_insurer_payments_insurer_id'), 'insurer_payments', ['insurer_id'])
    op.create_index(op.f('ix_insurer_payments_branch_id'), 'insurer_payments', ['branch_id'])


def downgrade() -> None:
    op.drop_table('insurer_payments')
