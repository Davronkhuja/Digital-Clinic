"""hisob-fakturalar (invoices, invoice_lines), raqam ketma-ketligi, finance:discount ruxsati

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-13 20:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0018'
down_revision = '0017'
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
    op.execute(sa.schema.CreateSequence(sa.Sequence('invoice_number_seq')))
    op.create_table('invoices',
        sa.Column('number', sa.String(length=20), nullable=False),
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('doctor_id', sa.UUID(), nullable=True),
        sa.Column('appointment_id', sa.UUID(), nullable=True),
        sa.Column('encounter_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.Enum('Draft', 'Issued', 'PartiallyPaid', 'Paid', 'Cancelled', name='status', native_enum=False,
                                    create_constraint=True, length=14), nullable=False),
        sa.Column('subtotal', sa.Numeric(14, 2), nullable=False),
        sa.Column('discount_total', sa.Numeric(14, 2), nullable=False),
        sa.Column('total', sa.Numeric(14, 2), nullable=False),
        sa.Column('vat_total', sa.Numeric(14, 2), nullable=False),
        sa.Column('discount_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('discount_reason', sa.String(length=300), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_reason', sa.String(length=300), nullable=True),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        *_base(),
        sa.CheckConstraint('subtotal >= 0 AND discount_total >= 0 AND total >= 0 AND vat_total >= 0', name=op.f('ck_invoices_amounts_non_negative')),
        sa.CheckConstraint('total = subtotal - discount_total', name=op.f('ck_invoices_total_consistent')),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], name=op.f('fk_invoices_appointment_id_appointments'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_invoices_branch_id_branches'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['doctor_id'], ['staff.id'], name=op.f('fk_invoices_doctor_id_staff'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], name=op.f('fk_invoices_encounter_id_encounters'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_invoices_patient_id_patients'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_invoices')),
        sa.UniqueConstraint('number', name=op.f('uq_invoices_number')),
    )
    op.create_index(op.f('ix_invoices_branch_id'), 'invoices', ['branch_id'])
    op.create_index(op.f('ix_invoices_patient_id'), 'invoices', ['patient_id'])
    op.create_index(op.f('ix_invoices_status'), 'invoices', ['status'])

    op.create_table('invoice_lines',
        sa.Column('invoice_id', sa.UUID(), nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('doctor_id', sa.UUID(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('mxik', sa.String(length=17), nullable=False),
        sa.Column('package_code', sa.String(length=10), nullable=False),
        sa.Column('vat_percent', sa.Numeric(5, 2), nullable=False),
        sa.Column('unit_price', sa.Numeric(14, 2), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('line_discount', sa.Numeric(14, 2), nullable=False),
        sa.Column('invoice_discount_share', sa.Numeric(14, 2), nullable=False),
        sa.Column('net_total', sa.Numeric(14, 2), nullable=False),
        sa.Column('vat_amount', sa.Numeric(14, 2), nullable=False),
        *_base(),
        sa.CheckConstraint('quantity > 0 AND unit_price >= 0', name=op.f('ck_invoice_lines_qty_price_valid')),
        sa.CheckConstraint('line_discount >= 0 AND invoice_discount_share >= 0 AND net_total >= 0 AND vat_amount >= 0',
                           name=op.f('ck_invoice_lines_amounts_non_negative')),
        sa.CheckConstraint('net_total = quantity * unit_price - line_discount - invoice_discount_share', name=op.f('ck_invoice_lines_net_consistent')),
        sa.ForeignKeyConstraint(['doctor_id'], ['staff.id'], name=op.f('fk_invoice_lines_doctor_id_staff'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_invoice_lines_invoice_id_invoices'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], name=op.f('fk_invoice_lines_service_id_services'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_invoice_lines')),
    )
    op.create_index(op.f('ix_invoice_lines_invoice_id'), 'invoice_lines', ['invoice_id'])

    op.execute("""
        INSERT INTO permissions (code, description) VALUES ('finance:discount', 'Hisob-fakturaga chegirma berish')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'finance:discount' AND r.code IN ('admin', 'cashier')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'finance:discount'")
    op.drop_table('invoice_lines')
    op.drop_table('invoices')
    op.execute(sa.schema.DropSequence(sa.Sequence('invoice_number_seq')))
