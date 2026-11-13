"""bemor manbasi (patients.source) va qayta ko'rik sanasi (encounters.recall_date)

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-18 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('patients', sa.Column('source', sa.String(length=20), nullable=True))
    op.create_check_constraint(op.f('ck_patients_source_values'), 'patients',
                               "source IS NULL OR source IN ('reklama', 'tavsiya', 'instagram', 'onlayn', 'boshqa')")
    op.add_column('encounters', sa.Column('recall_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('encounters', 'recall_date')
    op.drop_constraint(op.f('ck_patients_source_values'), 'patients', type_='check')
    op.drop_column('patients', 'source')
