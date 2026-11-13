"""xabarlar: rozilik, shablonlar, xabar logi, bemor tili, tungi vaqt sozlamasi

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-17 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None


def _base() -> list:
    return [
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
    ]


def _channel(name: str = 'channel') -> sa.Enum:
    return sa.Enum('SMS', 'Telegram', name=name, native_enum=False, create_constraint=True, length=8)


def upgrade() -> None:
    op.add_column('patients', sa.Column('language', sa.String(length=2), server_default='uz', nullable=False))
    op.add_column('clinic_settings', sa.Column('quiet_start_hour', sa.Integer(), server_default='21', nullable=False))
    op.add_column('clinic_settings', sa.Column('quiet_end_hour', sa.Integer(), server_default='8', nullable=False))

    op.create_table('patient_consents',
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('channel', _channel(), nullable=False),
        sa.Column('status', sa.Enum('Granted', 'Revoked', name='status', native_enum=False, create_constraint=True, length=7), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=True),
        *_base(),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_patient_consents_patient_id_patients'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_patient_consents')),
        sa.UniqueConstraint('patient_id', 'channel', name=op.f('uq_patient_consents_patient_id')),
    )
    op.create_index(op.f('ix_patient_consents_patient_id'), 'patient_consents', ['patient_id'])

    op.create_table('message_templates',
        sa.Column('key', sa.String(length=40), nullable=False),
        sa.Column('language', sa.String(length=2), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        *_base(),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_message_templates')),
        sa.UniqueConstraint('key', 'language', name=op.f('uq_message_templates_key')),
    )

    op.create_table('telegram_links',
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('chat_id', sa.String(length=30), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        *_base(),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_telegram_links_patient_id_patients'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_telegram_links')),
        sa.UniqueConstraint('chat_id', 'patient_id', name=op.f('uq_telegram_links_chat_id')),
    )
    op.create_index(op.f('ix_telegram_links_chat_id'), 'telegram_links', ['chat_id'])
    op.create_index(op.f('ix_telegram_links_patient_id'), 'telegram_links', ['patient_id'])

    op.create_table('messages',
        sa.Column('patient_id', sa.UUID(), nullable=True),
        sa.Column('channel', _channel(), nullable=False),
        sa.Column('to_address', sa.String(length=60), nullable=False),
        sa.Column('kind', sa.String(length=40), nullable=False),
        sa.Column('language', sa.String(length=2), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('Queued', 'Sent', 'Failed', 'Skipped', name='status', native_enum=False, create_constraint=True, length=7), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_error', sa.String(length=300), nullable=True),
        sa.Column('provider_message_id', sa.String(length=100), nullable=True),
        sa.Column('sms_segments', sa.Integer(), server_default='0', nullable=False),
        sa.Column('appointment_id', sa.UUID(), nullable=True),
        sa.Column('dedupe_key', sa.String(length=120), nullable=True),
        sa.Column('skip_reason', sa.String(length=120), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], name=op.f('fk_messages_appointment_id_appointments'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_messages_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_messages_patient_id_patients'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_messages')),
    )
    op.create_index(op.f('ix_messages_appointment_id'), 'messages', ['appointment_id'])
    op.create_index(op.f('ix_messages_branch_id'), 'messages', ['branch_id'])
    op.create_index(op.f('ix_messages_kind'), 'messages', ['kind'])
    op.create_index(op.f('ix_messages_patient_id'), 'messages', ['patient_id'])
    op.create_index('ix_messages_due', 'messages', ['status', 'scheduled_at'])
    op.create_index('uq_messages_dedupe', 'messages', ['dedupe_key'], unique=True, postgresql_where=sa.text('dedupe_key IS NOT NULL'))


    op.execute("""
        INSERT INTO permissions (code, description) VALUES ('messages:read', 'Xabarlar logi va SMS hisobini ko''rish')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'messages:read' AND r.code IN ('admin', 'receptionist', 'senior_receptionist')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'messages:read'")
    op.drop_table('messages')
    op.drop_table('telegram_links')
    op.drop_table('message_templates')
    op.drop_table('patient_consents')
    op.drop_column('clinic_settings', 'quiet_end_hour')
    op.drop_column('clinic_settings', 'quiet_start_hour')
    op.drop_column('patients', 'language')
