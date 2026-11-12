"""kassa smenalari, Z-raqam ketma-ketligi, to'lov/qaytarishda shift_id, finance:shifts ruxsati

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-15 10:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.schema.CreateSequence(sa.Sequence('z_number_seq')))
    op.create_table('cash_shifts',
        sa.Column('opened_by', sa.UUID(), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('opening_cash', sa.Numeric(14, 2), nullable=False),
        sa.Column('status', sa.Enum('Open', 'Closed', name='status', native_enum=False, create_constraint=True, length=6), nullable=False),
        sa.Column('closed_by', sa.UUID(), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('counted_cash', sa.Numeric(14, 2), nullable=True),
        sa.Column('expected_cash', sa.Numeric(14, 2), nullable=True),
        sa.Column('difference', sa.Numeric(14, 2), nullable=True),
        sa.Column('z_number', sa.String(length=12), nullable=True),
        sa.Column('z_data', postgresql.JSONB(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('opening_cash >= 0 AND (counted_cash IS NULL OR counted_cash >= 0)', name=op.f('ck_cash_shifts_cash_non_negative')),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_cash_shifts_branch_id_branches'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_cash_shifts')),
        sa.UniqueConstraint('z_number', name=op.f('uq_cash_shifts_z_number')),
    )
    op.create_index(op.f('ix_cash_shifts_branch_id'), 'cash_shifts', ['branch_id'])
    op.create_index(op.f('ix_cash_shifts_opened_by'), 'cash_shifts', ['opened_by'])
    op.create_index('uq_cash_shifts_one_open_per_user', 'cash_shifts', ['opened_by'], unique=True, postgresql_where=sa.text("status = 'Open'"))

    for table in ('payments', 'payment_refunds'):
        op.add_column(table, sa.Column('shift_id', sa.UUID(), nullable=True))
        op.create_foreign_key(op.f(f'fk_{table}_shift_id_cash_shifts'), table, 'cash_shifts', ['shift_id'], ['id'], ondelete='RESTRICT')
        op.create_index(op.f(f'ix_{table}_shift_id'), table, ['shift_id'])

    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('finance:shifts', 'Hamma kassa smenalarini ko''rish va boshqa kassir smenasini yopish')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'finance:shifts' AND r.code = 'admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'finance:shifts'")
    for table in ('payment_refunds', 'payments'):
        op.drop_index(op.f(f'ix_{table}_shift_id'), table_name=table)
        op.drop_constraint(op.f(f'fk_{table}_shift_id_cash_shifts'), table, type_='foreignkey')
        op.drop_column(table, 'shift_id')
    op.drop_table('cash_shifts')
    op.execute(sa.schema.DropSequence(sa.Sequence('z_number_seq')))
