"""patients.merged_into_id: birlashtirilgan dublikat qaysi bemorga o'tgani

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('patients', sa.Column('merged_into_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_patients_merged_into_id_patients'), 'patients', 'patients',
                          ['merged_into_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(op.f('fk_patients_merged_into_id_patients'), 'patients', type_='foreignkey')
    op.drop_column('patients', 'merged_into_id')
