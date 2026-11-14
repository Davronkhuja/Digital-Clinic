"""shifokor bir nechta filialda: staff_branches, jadval va istisnolar filial bo'yicha, filiallar orasida kesishmaslik

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-24 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0041'
down_revision = '0040'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('staff_branches',
        sa.Column('staff_id', sa.UUID(), nullable=False),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], name=op.f('fk_staff_branches_staff_id_staff'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_staff_branches_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_staff_branches')),
        sa.UniqueConstraint('staff_id', 'branch_id', name=op.f('uq_staff_branches_staff_id')),
    )
    op.create_index(op.f('ix_staff_branches_staff_id'), 'staff_branches', ['staff_id'])
    op.create_index(op.f('ix_staff_branches_branch_id'), 'staff_branches', ['branch_id'])
    op.execute("INSERT INTO staff_branches (staff_id, branch_id) SELECT id, branch_id FROM staff")

    for table in ('doctor_schedules', 'schedule_exceptions'):
        op.add_column(table, sa.Column('branch_id', sa.UUID(), nullable=True))
        op.execute(f"UPDATE {table} t SET branch_id = s.branch_id FROM staff s WHERE t.staff_id = s.id")
        op.alter_column(table, 'branch_id', nullable=False)
        op.create_foreign_key(op.f(f'fk_{table}_branch_id_branches'), table, 'branches', ['branch_id'], ['id'], ondelete='RESTRICT')
        op.create_index(op.f(f'ix_{table}_branch_id'), table, ['branch_id'])

    op.drop_constraint(op.f('uq_doctor_schedules_staff_id'), 'doctor_schedules', type_='unique')
    op.create_unique_constraint(op.f('uq_doctor_schedules_staff_id'), 'doctor_schedules', ['staff_id', 'branch_id', 'weekday'])
    op.execute("""
        ALTER TABLE doctor_schedules ADD CONSTRAINT no_cross_branch_schedule
        EXCLUDE USING gist (staff_id WITH =, weekday WITH =, branch_id WITH <>,
                            tsrange(timestamp '2000-01-01' + start_time, timestamp '2000-01-01' + end_time) WITH &&)
    """)
    op.execute("""
        ALTER TABLE schedule_exceptions ADD CONSTRAINT no_cross_branch_extra_work
        EXCLUDE USING gist (staff_id WITH =, branch_id WITH <>, tsrange(date_from + start_time, date_from + end_time) WITH &&)
        WHERE (kind = 'ExtraWork')
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE schedule_exceptions DROP CONSTRAINT no_cross_branch_extra_work")
    op.execute("ALTER TABLE doctor_schedules DROP CONSTRAINT no_cross_branch_schedule")
    op.drop_constraint(op.f('uq_doctor_schedules_staff_id'), 'doctor_schedules', type_='unique')
    # Bir nechta filialdagi qatorlar bo'lsa asosiy filialdagilari qoladi
    op.execute("DELETE FROM doctor_schedules d USING staff s WHERE d.staff_id = s.id AND d.branch_id <> s.branch_id")
    op.create_unique_constraint(op.f('uq_doctor_schedules_staff_id'), 'doctor_schedules', ['staff_id', 'weekday'])
    for table in ('schedule_exceptions', 'doctor_schedules'):
        op.drop_index(op.f(f'ix_{table}_branch_id'), table_name=table)
        op.drop_constraint(op.f(f'fk_{table}_branch_id_branches'), table, type_='foreignkey')
        op.drop_column(table, 'branch_id')
    op.drop_table('staff_branches')
