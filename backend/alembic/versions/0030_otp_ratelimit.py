"""OTP kodlar va ochiq endpointlar tezlik cheklovi

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-18 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0030'
down_revision = '0029'
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
    op.create_table('otp_codes',
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('purpose', sa.String(length=20), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip', sa.String(length=45), nullable=True),
        *_base(),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_otp_codes')),
    )
    op.create_index(op.f('ix_otp_codes_phone'), 'otp_codes', ['phone'])
    op.create_table('rate_events',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('action', sa.String(length=30), nullable=False),
        *_base(),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_rate_events')),
    )
    op.create_index('ix_rate_events_lookup', 'rate_events', ['action', 'key', 'created_at'])


def downgrade() -> None:
    op.drop_table('rate_events')
    op.drop_table('otp_codes')
