"""kabinetlar, shifokorning standart kabineti va bir vaqtga ikkita qabulni taqiqlovchi exclusion cheklovlar

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-11 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

BUSY = "status IN ('Scheduled', 'Completed')"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table('rooms',
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_rooms_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_rooms')),
    )
    op.create_index(op.f('ix_rooms_branch_id'), 'rooms', ['branch_id'])
    op.create_index('uq_rooms_branch_name_lower', 'rooms', ['branch_id', sa.text('lower(name)')], unique=True)

    op.add_column('staff', sa.Column('default_room_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_staff_default_room_id_rooms'), 'staff', 'rooms', ['default_room_id'], ['id'],
                          ondelete='SET NULL')
    op.add_column('appointments', sa.Column('room_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_appointments_room_id_rooms'), 'appointments', 'rooms', ['room_id'], ['id'],
                          ondelete='RESTRICT')
    op.create_index(op.f('ix_appointments_room_id'), 'appointments', ['room_id'])

    op.execute(f"""
        ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap
        EXCLUDE USING gist (doctor_id WITH =, tstzrange(starts_at, ends_at) WITH &&) WHERE ({BUSY})
    """)
    op.execute(f"""
        ALTER TABLE appointments ADD CONSTRAINT no_room_overlap
        EXCLUDE USING gist (room_id WITH =, tstzrange(starts_at, ends_at) WITH &&)
        WHERE ({BUSY} AND room_id IS NOT NULL)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE appointments DROP CONSTRAINT no_room_overlap")
    op.execute("ALTER TABLE appointments DROP CONSTRAINT no_doctor_overlap")
    op.drop_index(op.f('ix_appointments_room_id'), table_name='appointments')
    op.drop_constraint(op.f('fk_appointments_room_id_rooms'), 'appointments', type_='foreignkey')
    op.drop_column('appointments', 'room_id')
    op.drop_constraint(op.f('fk_staff_default_room_id_rooms'), 'staff', type_='foreignkey')
    op.drop_column('staff', 'default_room_id')
    op.drop_table('rooms')
