"""shifokor haftalik jadvali (doctor_schedules) va istisnolar (schedule_exceptions)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-11 15:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
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
    op.create_table('doctor_schedules',
        sa.Column('staff_id', sa.UUID(), nullable=False),
        sa.Column('weekday', sa.SmallInteger(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('break_start', sa.Time(), nullable=True),
        sa.Column('break_end', sa.Time(), nullable=True),
        *_base(),
        sa.CheckConstraint('weekday BETWEEN 0 AND 6', name=op.f('ck_doctor_schedules_weekday_range')),
        sa.CheckConstraint('end_time > start_time', name=op.f('ck_doctor_schedules_hours_order')),
        sa.CheckConstraint(
            '(break_start IS NULL AND break_end IS NULL) OR (break_start IS NOT NULL AND break_end IS NOT NULL '
            'AND break_start < break_end AND break_start >= start_time AND break_end <= end_time)',
            name=op.f('ck_doctor_schedules_break_valid')),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], name=op.f('fk_doctor_schedules_staff_id_staff'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_doctor_schedules')),
        sa.UniqueConstraint('staff_id', 'weekday', name=op.f('uq_doctor_schedules_staff_id')),
    )
    op.create_index(op.f('ix_doctor_schedules_staff_id'), 'doctor_schedules', ['staff_id'])

    op.create_table('schedule_exceptions',
        sa.Column('staff_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.Enum('DayOff', 'Vacation', 'Sick', 'ExtraWork', name='kind', native_enum=False,
                                  create_constraint=True, length=12), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=False),
        sa.Column('date_to', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('break_start', sa.Time(), nullable=True),
        sa.Column('break_end', sa.Time(), nullable=True),
        sa.Column('note', sa.String(length=200), nullable=True),
        *_base(),
        sa.CheckConstraint('date_to >= date_from', name=op.f('ck_schedule_exceptions_dates_order')),
        sa.CheckConstraint(
            "(kind = 'ExtraWork' AND start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time "
            "AND date_from = date_to) OR (kind <> 'ExtraWork' AND start_time IS NULL AND end_time IS NULL)",
            name=op.f('ck_schedule_exceptions_kind_hours')),
        sa.CheckConstraint(
            "(break_start IS NULL AND break_end IS NULL) OR (kind = 'ExtraWork' AND break_start IS NOT NULL "
            "AND break_end IS NOT NULL AND break_start < break_end AND break_start >= start_time AND break_end <= end_time)",
            name=op.f('ck_schedule_exceptions_break_valid')),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], name=op.f('fk_schedule_exceptions_staff_id_staff'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_schedule_exceptions')),
    )
    op.create_index(op.f('ix_schedule_exceptions_staff_id'), 'schedule_exceptions', ['staff_id'])
    op.create_index(op.f('ix_schedule_exceptions_date_from'), 'schedule_exceptions', ['date_from'])


def downgrade() -> None:
    op.drop_table('schedule_exceptions')
    op.drop_table('doctor_schedules')
