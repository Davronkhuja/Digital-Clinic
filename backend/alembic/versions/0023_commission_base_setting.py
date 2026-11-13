"""foiz asosi sozlamasi: clinic_settings.commission_base, qoida asosi ixtiyoriy, yozuvda base_kind nusxasi

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-16 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('clinic_settings', sa.Column('commission_base', sa.String(length=10), server_default='NetOfVat', nullable=False))
    op.alter_column('commission_rules', 'base', existing_type=sa.String(length=10), nullable=True)
    op.add_column('commission_entries', sa.Column(
        'base_kind', sa.Enum('WithVat', 'NetOfVat', name='base_kind', native_enum=False, create_constraint=True, length=10), nullable=True))
    # mavjud yozuvlar qoida asosi (yoki avvalgi standart WithVat) bilan hisoblangan
    op.execute("""
        UPDATE commission_entries e SET base_kind = COALESCE((SELECT r.base FROM commission_rules r WHERE r.id = e.rule_id), 'WithVat')
    """)


def downgrade() -> None:
    op.drop_column('commission_entries', 'base_kind')
    op.execute("UPDATE commission_rules SET base = 'WithVat' WHERE base IS NULL")
    op.alter_column('commission_rules', 'base', existing_type=sa.String(length=10), nullable=False)
    op.drop_column('clinic_settings', 'commission_base')
