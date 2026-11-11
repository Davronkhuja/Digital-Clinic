"""kutish ro'yxati (waitlist)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-11 17:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('waitlist',
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('doctor_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(length=60), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=False),
        sa.Column('date_to', sa.Date(), nullable=True),
        sa.Column('status', sa.Enum('Waiting', 'Booked', 'Cancelled', name='status', native_enum=False,
                                    create_constraint=True, length=10), nullable=False),
        sa.Column('appointment_id', sa.UUID(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('date_to IS NULL OR date_to >= date_from', name=op.f('ck_waitlist_dates_order')),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], name=op.f('fk_waitlist_appointment_id_appointments'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_waitlist_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['doctor_id'], ['staff.id'], name=op.f('fk_waitlist_doctor_id_staff'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_waitlist_patient_id_patients'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_waitlist')),
    )
    op.create_index(op.f('ix_waitlist_branch_id'), 'waitlist', ['branch_id'])
    op.create_index(op.f('ix_waitlist_doctor_id'), 'waitlist', ['doctor_id'])
    op.create_index(op.f('ix_waitlist_patient_id'), 'waitlist', ['patient_id'])
    op.create_index('uq_waitlist_waiting', 'waitlist', ['patient_id', 'doctor_id'], unique=True,
                    postgresql_where=sa.text("status = 'Waiting'"))


def downgrade() -> None:
    op.drop_table('waitlist')
