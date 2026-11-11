"""INN ma'lumotnomasi va tuzilgan retsept maydonlari (inn, route, instructions)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-12 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

ROUTES = ("Oral", "Intravenous", "Intramuscular", "Subcutaneous", "Topical", "Inhalation", "Sublingual", "Rectal",
          "Ophthalmic", "Nasal", "Otic", "Vaginal")


def upgrade() -> None:
    op.create_table('inn_drugs',
        sa.Column('inn', sa.String(length=200), nullable=False),
        sa.Column('group_uz', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_inn_drugs')),
    )
    op.create_index('uq_inn_drugs_inn_lower', 'inn_drugs', [sa.text('lower(inn)')], unique=True)
    op.add_column('prescriptions', sa.Column('inn', sa.String(length=200), nullable=True))
    op.add_column('prescriptions', sa.Column('route', sa.String(length=16), nullable=True))
    op.add_column('prescriptions', sa.Column('instructions', sa.Text(), nullable=True))
    values = ", ".join(f"'{r}'" for r in ROUTES)
    op.create_check_constraint(op.f('ck_prescriptions_route'), 'prescriptions', f'route IN ({values})')


def downgrade() -> None:
    op.drop_constraint(op.f('ck_prescriptions_route'), 'prescriptions', type_='check')
    op.drop_column('prescriptions', 'instructions')
    op.drop_column('prescriptions', 'route')
    op.drop_column('prescriptions', 'inn')
    op.drop_table('inn_drugs')
