"""buxgalteriya eksporti: ustun xaritasi, format va exports:read ruxsati

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-28 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0045'
down_revision = '0044'
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
    op.create_table('export_columns',
        sa.Column('dataset', sa.String(length=30), nullable=False),
        sa.Column('key', sa.String(length=40), nullable=False),
        sa.Column('header', sa.String(length=80), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        *_base(),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_export_columns')),
    )
    op.create_index('uq_export_columns_dataset_key', 'export_columns', ['dataset', 'key'], unique=True)
    op.create_table('export_format',
        sa.Column('date_format', sa.String(length=3), server_default='iso', nullable=False),
        sa.Column('decimal_separator', sa.String(length=1), server_default='.', nullable=False),
        sa.Column('csv_delimiter', sa.String(length=3), server_default=';', nullable=False),
        *_base(),
        sa.CheckConstraint("date_format IN ('iso', 'dmy')", name=op.f('ck_export_format_date_format_values')),
        sa.CheckConstraint("decimal_separator IN ('.', ',')", name=op.f('ck_export_format_decimal_separator_values')),
        sa.CheckConstraint("csv_delimiter IN (';', ',', 'tab')", name=op.f('ck_export_format_csv_delimiter_values')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_export_format')),
    )
    op.execute("""
        INSERT INTO permissions (code, description) VALUES
          ('exports:read', 'Buxgalteriya eksporti (sotuvlar, to''lovlar, kassa smenalari, ombor harakatlari, shifokor foizlari): Excel va CSV')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'exports:read' AND r.code = 'admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'exports:read'")
    op.drop_table('export_format')
    op.drop_table('export_columns')
