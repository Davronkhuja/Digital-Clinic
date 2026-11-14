"""xodimlar bildirishnomalari (ombor ogohlantirishlari)

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-23 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None


def _base() -> list:
    return [
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table('notifications',
        sa.Column('permission', sa.String(length=60), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('link', sa.String(length=200), nullable=True),
        sa.Column('dedupe_key', sa.String(length=120), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_notifications_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
        sa.UniqueConstraint('dedupe_key', name=op.f('uq_notifications_dedupe_key')),
    )
    op.create_index(op.f('ix_notifications_branch_id'), 'notifications', ['branch_id'])
    op.create_index('ix_notifications_branch_created', 'notifications', ['branch_id', 'created_at'])
    op.create_table('notification_reads',
        sa.Column('notification_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        *_base(),
        sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], name=op.f('fk_notification_reads_notification_id_notifications'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_reads')),
        sa.UniqueConstraint('notification_id', 'user_id', name=op.f('uq_notification_reads_notification_id')),
    )
    op.create_index(op.f('ix_notification_reads_notification_id'), 'notification_reads', ['notification_id'])
    op.create_index(op.f('ix_notification_reads_user_id'), 'notification_reads', ['user_id'])


def downgrade() -> None:
    op.drop_table('notification_reads')
    op.drop_table('notifications')
