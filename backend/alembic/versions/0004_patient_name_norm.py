"""patients.name_norm: normallashtirilgan ism (kirill/lotin, apostrof, registr), indekslangan

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11 12:00:00
"""
from alembic import op
import sqlalchemy as sa

from app.core.names import normalize_name

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('patients', sa.Column('name_norm', sa.String(length=200), nullable=True))
    conn = op.get_bind()
    for pid, name in conn.execute(sa.text("SELECT id, full_name FROM patients")).all():
        conn.execute(sa.text("UPDATE patients SET name_norm = :n WHERE id = :i"), {"n": normalize_name(name), "i": pid})
    op.alter_column('patients', 'name_norm', nullable=False)
    op.create_index(op.f('ix_patients_name_norm'), 'patients', ['name_norm'])


def downgrade() -> None:
    op.drop_index(op.f('ix_patients_name_norm'), table_name='patients')
    op.drop_column('patients', 'name_norm')
