"""uchrashuvlar timestamptz (starts_at/ends_at), qabul turlari va shifokor standart davomiyligi

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-11 13:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

TYPES = [("Konsultatsiya", 30), ("Takroriy ko'rik", 20), ("Qayta ko'rik", 20), ("Tekshiruv", 45),
         ("Laboratoriya", 15), ("Jarrohlik", 90), ("Boshqa", 30)]


def upgrade() -> None:
    op.create_table('appointment_types',
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('duration_min', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('duration_min BETWEEN 5 AND 480', name=op.f('ck_appointment_types_duration_range')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_appointment_types')),
    )
    op.create_index('uq_appointment_types_name_lower', 'appointment_types', [sa.text('lower(name)')], unique=True)
    for name, minutes in TYPES:
        op.execute(sa.text("INSERT INTO appointment_types (name, duration_min) VALUES (:n, :m) ON CONFLICT DO NOTHING")
                   .bindparams(n=name, m=minutes))

    op.add_column('staff', sa.Column('slot_minutes', sa.Integer(), server_default='30', nullable=False))
    op.create_check_constraint(op.f('ck_staff_slot_minutes_range'), 'staff', 'slot_minutes BETWEEN 5 AND 480')

    # eski date + time (klinika vaqti) -> timestamptz; davomiylik: tur bo'yicha, bo'lmasa 30 daqiqa
    op.add_column('appointments', sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("""
        UPDATE appointments a SET
          starts_at = (a.date + a.time) AT TIME ZONE 'Asia/Tashkent',
          ends_at = (a.date + a.time) AT TIME ZONE 'Asia/Tashkent'
                    + make_interval(mins => COALESCE((SELECT t.duration_min FROM appointment_types t
                                                      WHERE lower(t.name) = lower(a.type)), 30))
    """)
    op.alter_column('appointments', 'starts_at', nullable=False)
    op.alter_column('appointments', 'ends_at', nullable=False)
    op.create_check_constraint(op.f('ck_appointments_ends_after_start'), 'appointments', 'ends_at > starts_at')
    op.create_index(op.f('ix_appointments_starts_at'), 'appointments', ['starts_at'])
    op.drop_index(op.f('ix_appointments_date'), table_name='appointments')
    op.drop_column('appointments', 'date')
    op.drop_column('appointments', 'time')


def downgrade() -> None:
    op.add_column('appointments', sa.Column('date', sa.Date(), nullable=True))
    op.add_column('appointments', sa.Column('time', sa.Time(), nullable=True))
    op.execute("""
        UPDATE appointments SET date = (starts_at AT TIME ZONE 'Asia/Tashkent')::date,
                                time = (starts_at AT TIME ZONE 'Asia/Tashkent')::time
    """)
    op.alter_column('appointments', 'date', nullable=False)
    op.alter_column('appointments', 'time', nullable=False)
    op.create_index(op.f('ix_appointments_date'), 'appointments', ['date'])
    op.drop_index(op.f('ix_appointments_starts_at'), table_name='appointments')
    op.drop_constraint(op.f('ck_appointments_ends_after_start'), 'appointments', type_='check')
    op.drop_column('appointments', 'ends_at')
    op.drop_column('appointments', 'starts_at')
    op.drop_constraint(op.f('ck_staff_slot_minutes_range'), 'staff', type_='check')
    op.drop_column('staff', 'slot_minutes')
    op.drop_table('appointment_types')
