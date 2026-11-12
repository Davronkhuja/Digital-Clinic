"""ma'lumotnomalarda verified/source (MKB-10, INN, lab tahlil va me'yor) va natijada ref_verified

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-13 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None

TABLES = ('icd10_codes', 'inn_drugs', 'lab_tests', 'lab_reference_ranges')


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('verified', sa.Boolean(), server_default='false', nullable=False))
        op.add_column(table, sa.Column('source', sa.String(length=200), nullable=True))
        # hozirgi yozuvlarning hammasi starter (namuna): tekshirilmagan
        op.execute(sa.text(f"UPDATE {table} SET source = 'starter (namuna)'"))
    op.add_column('lab_order_items', sa.Column('ref_verified', sa.Boolean(), nullable=True))
    # natijalarda solishtirilgan me'yor hozircha hammasi starter
    op.execute("UPDATE lab_order_items SET ref_verified = false WHERE flag IS NOT NULL")


def downgrade() -> None:
    op.drop_column('lab_order_items', 'ref_verified')
    for table in TABLES:
        op.drop_column(table, 'source')
        op.drop_column(table, 'verified')
